"""Utility helpers for workflow load and concurrency tests."""

from __future__ import annotations

import copy
import multiprocessing as mp
import queue as queue_module
import time
from collections.abc import Iterable
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.enums import EventType
from app.models import Business, Event, WorkflowDefinition
from app.services.event import EventService
from app.workflow_engine import WorkflowDispatcher, WorkflowExecutor
from app.workflow_engine.action_handlers import ActionHandlerRegistry
from app.workflow_engine.definition_provider import DatabaseDefinitionProvider


def create_business(db: Session, *, label: str = "load-test") -> Business:
    """Create a test tenant for load scenarios."""
    business = Business(
        id=uuid4(),
        name=f"{label}-{uuid4().hex[:8]}",
        email=f"{label}-{uuid4().hex[:8]}@example.test",
        phone="+27110000000",
    )
    db.add(business)
    db.flush()
    return business


def seed_definitions(
    db: Session,
    business_id: UUID,
    count: int,
    event_type: EventType,
    actions: list[dict[str, Any]],
) -> list[WorkflowDefinition]:
    """Bulk-create workflow definitions for a business."""
    definitions: list[WorkflowDefinition] = []
    for index in range(count):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=business_id,
            event_type=event_type,
            is_active=True,
            name=f"load-definition-{index:04d}",
            config={"actions": copy.deepcopy(actions)},
        )
        definitions.append(definition)
        db.add(definition)
    db.flush()
    return definitions


def seed_events(
    db: Session,
    business_id: UUID,
    count: int,
    event_type: EventType,
) -> list[Event]:
    """Bulk-create events for a business."""
    service = EventService(db)
    events: list[Event] = []
    for _ in range(count):
        events.append(
            service.create_event(
                business_id=business_id,
                event_type=event_type,
                entity_type="lead",
                entity_id=uuid4(),
                actor_id=None,
            )
        )
    db.flush()
    return events


def dispatch_events(db: Session, events: Iterable[Event]) -> int:
    """Dispatch a collection of events into workflow runs."""
    dispatcher = WorkflowDispatcher(
        db=db,
        definition_provider=DatabaseDefinitionProvider(db),
    )
    total_runs = 0
    try:
        for event in events:
            total_runs += len(dispatcher.dispatch(event))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return total_runs


def _new_process_session_factory() -> tuple[Any, Any]:
    """Create a fresh engine/session factory per worker process."""
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _worker_execute_loop(
    *,
    business_ids: list[str],
    max_iterations: int,
    queue: mp.Queue,
    handler_registry: ActionHandlerRegistry | None = None,
) -> None:
    worker_engine, worker_session_factory = _new_process_session_factory()
    session = worker_session_factory()
    executor = (
        WorkflowExecutor(session, handler_registry=handler_registry)
        if handler_registry is not None
        else WorkflowExecutor(session)
    )
    claimed_run_ids: list[str] = []
    executed_actions = 0
    errors: list[str] = []

    try:
        idle_rounds = 0
        for _ in range(max_iterations):
            claimed_in_round = False
            for business_id in business_ids:
                try:
                    result = executor.execute_next_run(UUID(business_id))
                    if result.get("claimed"):
                        session.commit()
                        claimed_in_round = True
                        run_id = result.get("run_id")
                        if isinstance(run_id, str):
                            claimed_run_ids.append(run_id)
                        executed_actions += int(result.get("executed_action_count", 0))
                    else:
                        session.rollback()
                except Exception as exc:  # pragma: no cover - surfaced in parent assertions
                    session.rollback()
                    errors.append(str(exc))

            if claimed_in_round:
                idle_rounds = 0
            else:
                idle_rounds += 1
                if idle_rounds >= 3:
                    break
    finally:
        session.close()
        worker_engine.dispose()
        queue.put(
            {
                "claimed_run_ids": claimed_run_ids,
                "executed_actions": executed_actions,
                "errors": errors,
            }
        )


def run_worker_pool(
    business_ids: list[UUID],
    worker_count: int,
    max_iterations: int = 100,
    timeout_seconds: int = 30,
    handler_registry: ActionHandlerRegistry | None = None,
) -> dict[str, Any]:
    """Spawn worker processes that run the executor loop concurrently."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()

    processes: list[mp.Process] = []
    for _ in range(worker_count):
        process = ctx.Process(
            target=_worker_execute_loop,
            kwargs={
                "business_ids": [str(business_id) for business_id in business_ids],
                "max_iterations": max_iterations,
                "queue": queue,
                "handler_registry": handler_registry,
            },
            daemon=True,
        )
        processes.append(process)
        process.start()

    deadline = time.monotonic() + timeout_seconds
    timed_out_workers = 0
    for process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        process.join(remaining)
        if process.is_alive():
            process.terminate()
            process.join(2.0)
            timed_out_workers += 1

    raw_results: list[dict[str, Any]] = []
    for _ in processes:
        try:
            raw_results.append(queue.get(timeout=1.0))
        except queue_module.Empty:
            break

    claimed_run_ids: list[str] = []
    errors: list[str] = []
    executed_actions = 0
    for item in raw_results:
        claimed_run_ids.extend(item.get("claimed_run_ids", []))
        executed_actions += int(item.get("executed_actions", 0))
        errors.extend(item.get("errors", []))

    return {
        "workers_started": worker_count,
        "workers_reported": len(raw_results),
        "timed_out_workers": timed_out_workers,
        "claimed_run_ids": claimed_run_ids,
        "runs_claimed": len(claimed_run_ids),
        "actions_executed": executed_actions,
        "errors": errors,
    }


def _worker_dispatch_loop(
    *,
    business_id: str,
    event_id: str,
    iterations: int,
    queue: mp.Queue,
) -> None:
    worker_engine, worker_session_factory = _new_process_session_factory()
    session = worker_session_factory()
    created_runs = 0
    errors: list[str] = []

    try:
        for _ in range(iterations):
            try:
                event = (
                    session.query(Event)
                    .filter(
                        Event.id == UUID(event_id),
                        Event.business_id == UUID(business_id),
                    )
                    .first()
                )
                if event is None:
                    break

                dispatcher = WorkflowDispatcher(
                    db=session,
                    definition_provider=DatabaseDefinitionProvider(session),
                )
                created_runs += len(dispatcher.dispatch(event))
                session.commit()
            except Exception as exc:  # pragma: no cover - surfaced in parent assertions
                session.rollback()
                errors.append(str(exc))
    finally:
        session.close()
        worker_engine.dispose()
        queue.put(
            {
                "created_runs": created_runs,
                "errors": errors,
            }
        )


def run_dispatch_race(
    *,
    business_id: UUID,
    event_id: UUID,
    worker_count: int,
    iterations_per_worker: int = 1,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Dispatch the same event from multiple processes to assert idempotency."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()

    processes: list[mp.Process] = []
    for _ in range(worker_count):
        process = ctx.Process(
            target=_worker_dispatch_loop,
            kwargs={
                "business_id": str(business_id),
                "event_id": str(event_id),
                "iterations": iterations_per_worker,
                "queue": queue,
            },
            daemon=True,
        )
        processes.append(process)
        process.start()

    deadline = time.monotonic() + timeout_seconds
    timed_out_workers = 0
    for process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        process.join(remaining)
        if process.is_alive():
            process.terminate()
            process.join(2.0)
            timed_out_workers += 1

    raw_results: list[dict[str, Any]] = []
    for _ in processes:
        try:
            raw_results.append(queue.get(timeout=1.0))
        except queue_module.Empty:
            break

    errors: list[str] = []
    created_runs = 0
    for item in raw_results:
        created_runs += int(item.get("created_runs", 0))
        errors.extend(item.get("errors", []))

    return {
        "workers_started": worker_count,
        "workers_reported": len(raw_results),
        "timed_out_workers": timed_out_workers,
        "created_runs": created_runs,
        "errors": errors,
    }
