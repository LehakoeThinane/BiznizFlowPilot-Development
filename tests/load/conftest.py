"""Shared fixtures and guards for load tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models import Business, Event, User, Workflow, WorkflowAction, WorkflowDefinition, WorkflowRun

_postgres_ready_cache: bool | None = None


def _normalize_arg(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def _is_explicit_load_run(config: pytest.Config) -> bool:
    normalized_args = [_normalize_arg(str(arg)) for arg in config.args]
    return any(
        arg.endswith("tests/load")
        or arg.endswith("tests/load/")
        or "/tests/load/" in arg
        for arg in normalized_args
    )


def _is_postgres_url() -> bool:
    return settings.database_url.lower().startswith("postgresql")


def _is_postgres_reachable() -> bool:
    global _postgres_ready_cache
    if _postgres_ready_cache is not None:
        return _postgres_ready_cache

    if not _is_postgres_url():
        _postgres_ready_cache = False
        return _postgres_ready_cache

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _postgres_ready_cache = True
    except SQLAlchemyError:
        _postgres_ready_cache = False
    return _postgres_ready_cache


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep load tests opt-in and skip when PostgreSQL is unavailable."""
    explicit_load_run = _is_explicit_load_run(config)

    if not explicit_load_run:
        marker = pytest.mark.skip(reason="Load tests are opt-in. Run `pytest tests/load/`.")
    elif not _is_postgres_reachable():
        marker = pytest.mark.skip(reason="Load tests require a reachable PostgreSQL DATABASE_URL.")
    else:
        return

    for item in items:
        path = _normalize_arg(str(item.fspath))
        if "/tests/load/" in path:
            item.add_marker(marker)


def _cleanup_business_scope(db, business_ids: list[UUID]) -> None:
    if not business_ids:
        return

    run_ids = [
        run_id
        for (run_id,) in (
            db.query(WorkflowRun.id)
            .filter(WorkflowRun.business_id.in_(business_ids))
            .all()
        )
    ]

    if run_ids:
        (
            db.query(WorkflowAction)
            .filter(WorkflowAction.run_id.in_(run_ids))
            .delete(synchronize_session=False)
        )

    (
        db.query(WorkflowRun)
        .filter(WorkflowRun.business_id.in_(business_ids))
        .delete(synchronize_session=False)
    )
    (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.business_id.in_(business_ids))
        .delete(synchronize_session=False)
    )
    (
        db.query(Event)
        .filter(Event.business_id.in_(business_ids))
        .delete(synchronize_session=False)
    )
    (
        db.query(Workflow)
        .filter(Workflow.business_id.in_(business_ids))
        .delete(synchronize_session=False)
    )
    (
        db.query(User)
        .filter(User.business_id.in_(business_ids))
        .delete(synchronize_session=False)
    )
    (
        db.query(Business)
        .filter(Business.id.in_(business_ids))
        .delete(synchronize_session=False)
    )


@pytest.fixture
def load_db():
    """Open one DB session for a load test and clean tracked business data afterward."""
    db = SessionLocal()
    created_business_ids: list[UUID] = []
    try:
        yield db, created_business_ids
    finally:
        try:
            db.rollback()
            _cleanup_business_scope(db, created_business_ids)
            db.commit()
        finally:
            db.close()
