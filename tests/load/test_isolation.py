"""Tenant-isolation load tests for workflow context resolution."""

from __future__ import annotations

from typing import Any

from app.core.enums import EventType, WorkflowActionStatus, WorkflowRunStatus
from app.models import Customer, Lead, WorkflowAction, WorkflowRun

from .handlers import build_isolation_handler_registry
from .utils import create_business, dispatch_events, run_worker_pool, seed_definitions, seed_events


def _create_lead_with_customer(*, db, business_id, email: str, name: str = "Load Lead") -> Lead:
    customer = Customer(
        business_id=business_id,
        name=name,
        email=email,
        phone="+27110000000",
        company="Load Test Co",
    )
    db.add(customer)
    db.flush()

    lead = Lead(
        business_id=business_id,
        customer_id=customer.id,
        status="new",
        source="load-test",
    )
    db.add(lead)
    db.flush()
    return lead


class TestWorkflowTenantIsolationLoad:
    def test_context_resolution_prevents_cross_tenant_access(self, load_db):
        """Resolver should never load entity context from a different business."""
        db, created_business_ids = load_db
        tenant_a = create_business(db, label="isolation-a")
        tenant_b = create_business(db, label="isolation-b")
        created_business_ids.extend([tenant_a.id, tenant_b.id])

        lead_a = _create_lead_with_customer(
            db=db,
            business_id=tenant_a.id,
            email="test@tenant-a.com",
            name="Tenant A Lead",
        )
        lead_b = _create_lead_with_customer(
            db=db,
            business_id=tenant_b.id,
            email="test@tenant-b.com",
            name="Tenant B Lead",
        )

        seed_definitions(
            db=db,
            business_id=tenant_a.id,
            count=1,
            event_type=EventType.LEAD_CREATED,
            actions=[{"action_type": "create_task", "title": "Processing lead: {lead.email}"}],
        )
        db.commit()

        events = seed_events(db, tenant_a.id, 2, EventType.LEAD_CREATED)
        # Valid event: tenant A entity.
        events[0].entity_type = "lead"
        events[0].entity_id = lead_a.id
        # Malicious/cross-tenant reference: tenant A event pointing at tenant B lead.
        events[1].entity_type = "lead"
        events[1].entity_id = lead_b.id
        db.commit()
        dispatch_events(db, events)

        result = run_worker_pool(
            business_ids=[tenant_a.id],
            worker_count=1,
            max_iterations=30,
            timeout_seconds=20,
            handler_registry=build_isolation_handler_registry(),
        )
        assert result["errors"] == []
        assert result["timed_out_workers"] == 0

        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.business_id == tenant_a.id)
            .order_by(WorkflowRun.created_at.asc())
            .all()
        )
        assert len(runs) == 2

        run_by_event = {str(run.event_id): run for run in runs}
        good_run = run_by_event[str(events[0].id)]
        bad_run = run_by_event[str(events[1].id)]

        good_action = (
            db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == good_run.id)
            .first()
        )
        bad_action = (
            db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == bad_run.id)
            .first()
        )
        assert good_action is not None
        assert bad_action is not None

        good_result: dict[str, Any] = good_action.result or {}
        bad_result: dict[str, Any] = bad_action.result or {}

        good_message = str(good_result.get("message", ""))
        bad_message = str(bad_result.get("message", ""))

        assert good_run.status == WorkflowRunStatus.COMPLETED
        assert good_action.status == WorkflowActionStatus.COMPLETED
        assert "test@tenant-a.com" in good_message
        assert "test@tenant-b.com" not in good_message

        assert bad_run.status == WorkflowRunStatus.FAILED
        assert bad_action.status == WorkflowActionStatus.FAILED
        assert "Missing template value" in bad_message
        assert "test@tenant-b.com" not in bad_message

    def test_concurrent_multi_tenant_execution_no_leakage(self, load_db):
        """Concurrent execution across tenants should not leak rendered context."""
        db, created_business_ids = load_db
        tenants = []
        for idx in range(5):
            tenant = create_business(db, label=f"isolation-{idx}")
            created_business_ids.append(tenant.id)
            tenants.append((tenant, f"tenant-{idx}.example"))

        lead_ids_by_tenant: dict[str, list] = {}
        for idx, (tenant, domain) in enumerate(tenants):
            lead_ids = []
            for lead_idx in range(10):
                lead = _create_lead_with_customer(
                    db=db,
                    business_id=tenant.id,
                    email=f"lead-{lead_idx}@{domain}",
                    name=f"Tenant {idx} Lead {lead_idx}",
                )
                lead_ids.append(lead.id)
            lead_ids_by_tenant[str(tenant.id)] = lead_ids

            seed_definitions(
                db=db,
                business_id=tenant.id,
                count=1,
                event_type=EventType.LEAD_CREATED,
                actions=[{"action_type": "create_task", "title": "{lead.email}"}],
            )
        db.commit()

        for tenant, _domain in tenants:
            events = seed_events(db, tenant.id, 10, EventType.LEAD_CREATED)
            lead_ids = lead_ids_by_tenant[str(tenant.id)]
            for event, lead_id in zip(events, lead_ids):
                event.entity_type = "lead"
                event.entity_id = lead_id
            db.commit()
            dispatch_events(db, events)

        result = run_worker_pool(
            business_ids=[tenant.id for tenant, _ in tenants],
            worker_count=5,
            max_iterations=400,
            timeout_seconds=60,
            handler_registry=build_isolation_handler_registry(),
        )
        assert result["errors"] == []
        assert result["timed_out_workers"] == 0

        tenant_domains = {str(tenant.id): domain for tenant, domain in tenants}
        all_domains = list(tenant_domains.values())

        for tenant, domain in tenants:
            actions = (
                db.query(WorkflowAction)
                .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
                .filter(WorkflowRun.business_id == tenant.id)
                .all()
            )
            assert len(actions) == 10
            assert all(action.status == WorkflowActionStatus.COMPLETED for action in actions)

            for action in actions:
                result_payload: dict[str, Any] = action.result or {}
                rendered = str(result_payload.get("message", ""))
                assert f"@{domain}" in rendered
                for other_domain in all_domains:
                    if other_domain == domain:
                        continue
                    assert f"@{other_domain}" not in rendered

