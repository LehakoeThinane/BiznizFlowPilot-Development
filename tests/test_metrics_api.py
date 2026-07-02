"""API tests for workflow metrics endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.enums import EventType, WorkflowActionStatus, WorkflowRunStatus
from app.core.security import create_access_token
from app.models import WorkflowAction, WorkflowDefinition, WorkflowRun
from app.schemas.auth import CurrentUser


def _auth_headers(user: CurrentUser) -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": str(user.user_id),
            "business_id": str(user.business_id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
        }
    )
    return {"Authorization": f"Bearer {token}"}


class TestMetricsApi:
    def test_metrics_are_scoped_to_current_tenant(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
        other_user: CurrentUser,
    ):
        # Definitions (owner tenant)
        owner_definitions = [
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.LEAD_CREATED,
                is_active=True,
                name="Owner Active 1",
                config={"actions": [{"action_type": "log", "message": "ok"}]},
            ),
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.TASK_CREATED,
                is_active=False,
                name="Owner Inactive",
                config={"actions": [{"action_type": "log", "message": "ok"}]},
            ),
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.TASK_ASSIGNED,
                is_active=True,
                name="Owner Active 2",
                config={"actions": [{"action_type": "log", "message": "ok"}]},
            ),
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.CUSTOM,
                is_active=True,
                name="Owner Deleted",
                config={"actions": [{"action_type": "log", "message": "ok"}]},
                deleted_at=datetime.now(timezone.utc),
            ),
        ]
        test_db.add_all(owner_definitions)

        # Definitions (other tenant)
        test_db.add(
            WorkflowDefinition(
                id=uuid4(),
                business_id=other_user.business_id,
                event_type=EventType.LEAD_CREATED,
                is_active=True,
                name="Other Tenant Definition",
                config={"actions": [{"action_type": "log", "message": "ok"}]},
            )
        )
        test_db.flush()

        # Runs (owner tenant): total=4, completed=2, failed=1, running=1
        owner_runs = [
            WorkflowRun(
                id=uuid4(),
                business_id=owner_user.business_id,
                status=WorkflowRunStatus.COMPLETED,
                definition_snapshot={},
                results={},
            ),
            WorkflowRun(
                id=uuid4(),
                business_id=owner_user.business_id,
                status=WorkflowRunStatus.COMPLETED,
                definition_snapshot={},
                results={},
            ),
            WorkflowRun(
                id=uuid4(),
                business_id=owner_user.business_id,
                status=WorkflowRunStatus.FAILED,
                definition_snapshot={},
                results={},
            ),
            WorkflowRun(
                id=uuid4(),
                business_id=owner_user.business_id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
            ),
        ]
        test_db.add_all(owner_runs)

        # Runs (other tenant)
        other_run = WorkflowRun(
            id=uuid4(),
            business_id=other_user.business_id,
            status=WorkflowRunStatus.COMPLETED,
            definition_snapshot={},
            results={},
        )
        test_db.add(other_run)
        test_db.flush()

        # Actions (owner tenant via run join):
        # total=5, completed=2, failed=2, retry_scheduled=1
        owner_actions = [
            WorkflowAction(
                run_id=owner_runs[0].id,
                action_type="log",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.COMPLETED,
            ),
            WorkflowAction(
                run_id=owner_runs[1].id,
                action_type="log",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.COMPLETED,
            ),
            WorkflowAction(
                run_id=owner_runs[2].id,
                action_type="log",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.FAILED,
            ),
            WorkflowAction(
                run_id=owner_runs[3].id,
                action_type="log",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.RETRY_SCHEDULED,
            ),
            WorkflowAction(
                run_id=owner_runs[3].id,
                action_type="log",
                parameters={},
                execution_order=1,
                status=WorkflowActionStatus.FAILED,
            ),
        ]
        test_db.add_all(owner_actions)

        # Action for other tenant should not be counted for owner.
        test_db.add(
            WorkflowAction(
                run_id=other_run.id,
                action_type="log",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.COMPLETED,
            )
        )
        test_db.commit()

        response = client.get(
            "/api/v1/metrics",
            headers=_auth_headers(owner_user),
        )
        assert response.status_code == 200
        body = response.json()

        assert body["business_id"] == str(owner_user.business_id)
        assert body["runs"] == {
            "total": 4,
            "completed": 2,
            "failed": 1,
            "running": 1,
        }
        assert body["actions"] == {
            "total": 5,
            "completed": 2,
            "failed": 2,
            "retry_scheduled": 1,
        }
        assert body["definitions"] == {
            "total": 3,
            "active": 2,
        }

    def test_metrics_rejects_cross_tenant_business_id_query(
        self,
        client,
        owner_user: CurrentUser,
        other_user: CurrentUser,
    ):
        response = client.get(
            f"/api/v1/metrics?business_id={other_user.business_id}",
            headers=_auth_headers(owner_user),
        )

        assert response.status_code == 403
        assert "another business" in response.json()["detail"]

    def test_metrics_accepts_explicit_current_business_id(
        self,
        client,
        owner_user: CurrentUser,
    ):
        response = client.get(
            f"/api/v1/metrics?business_id={owner_user.business_id}",
            headers=_auth_headers(owner_user),
        )
        assert response.status_code == 200
