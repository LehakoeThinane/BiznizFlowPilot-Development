"""API tests for workflow endpoint RBAC behavior."""

from __future__ import annotations

from app.core.security import create_access_token
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


def _workflow_payload(name: str = "Workflow RBAC Test") -> dict:
    return {
        "name": name,
        "description": "RBAC test workflow",
        "trigger_event_type": "lead_created",
        "enabled": True,
        "order": 0,
        "actions": [
            {
                "action_type": "log",
                "parameters": {"message": "hello"},
                "order": 0,
            }
        ],
    }


class TestWorkflowApiPermissions:
    """Permission checks for workflow CRUD endpoints."""

    def test_staff_create_returns_403(self, client, staff_user: CurrentUser):
        response = client.post(
            "/api/v1/workflows",
            headers=_auth_headers(staff_user),
            json=_workflow_payload(),
        )

        assert response.status_code == 403
        assert "not in allowed roles" in response.json()["detail"]

    def test_staff_update_returns_403(self, client, owner_user: CurrentUser, staff_user: CurrentUser):
        create_response = client.post(
            "/api/v1/workflows",
            headers=_auth_headers(owner_user),
            json=_workflow_payload(name="Owner Created Workflow"),
        )
        assert create_response.status_code == 201
        workflow_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/v1/workflows/{workflow_id}",
            headers=_auth_headers(staff_user),
            json={"name": "Unauthorized Update"},
        )

        assert update_response.status_code == 403
        assert "not in allowed roles" in update_response.json()["detail"]

    def test_staff_delete_returns_403(self, client, owner_user: CurrentUser, staff_user: CurrentUser):
        create_response = client.post(
            "/api/v1/workflows",
            headers=_auth_headers(owner_user),
            json=_workflow_payload(name="Delete Guard"),
        )
        assert create_response.status_code == 201
        workflow_id = create_response.json()["id"]

        delete_response = client.delete(
            f"/api/v1/workflows/{workflow_id}",
            headers=_auth_headers(staff_user),
        )

        assert delete_response.status_code == 403
        assert "not in allowed roles" in delete_response.json()["detail"]

    def test_staff_toggle_returns_403(self, client, owner_user: CurrentUser, staff_user: CurrentUser):
        create_response = client.post(
            "/api/v1/workflows",
            headers=_auth_headers(owner_user),
            json=_workflow_payload(name="Toggle Guard"),
        )
        assert create_response.status_code == 201
        workflow_id = create_response.json()["id"]

        toggle_response = client.patch(
            f"/api/v1/workflows/{workflow_id}/toggle?enabled=false",
            headers=_auth_headers(staff_user),
        )

        assert toggle_response.status_code == 403
        assert "not in allowed roles" in toggle_response.json()["detail"]


class TestWorkflowApiRoutes:
    """Route matching regressions."""

    def test_runs_list_route_is_not_captured_by_workflow_id(self, client, owner_user: CurrentUser):
        response = client.get(
            "/api/v1/workflows/runs",
            headers=_auth_headers(owner_user),
        )

        assert response.status_code == 200
        body = response.json()
        assert "runs" in body
        assert isinstance(body["runs"], list)
