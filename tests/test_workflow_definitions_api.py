"""API tests for workflow definition CRUD and validation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import EventType
from app.core.security import create_access_token
from app.models import WorkflowDefinition
from app.repositories.workflow import WorkflowDefinitionRepository
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


class TestWorkflowDefinitionCreate:
    """Create endpoint behavior."""

    def test_owner_can_create_definition(self, client, owner_user: CurrentUser):
        response = client.post(
            "/api/v1/workflow-definitions",
            headers=_auth_headers(owner_user),
            json={
                "event_type": "lead_created",
                "name": "Lead Definition",
                "is_active": True,
                "config": {
                    "actions": [
                        {
                            "action_type": "log",
                            "message": "created",
                        }
                    ]
                },
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Lead Definition"
        assert body["event_type"] == "lead_created"
        assert body["config"]["actions"][0]["action_type"] == "log"

    def test_staff_cannot_create_definition(self, client, staff_user: CurrentUser):
        response = client.post(
            "/api/v1/workflow-definitions",
            headers=_auth_headers(staff_user),
            json={
                "event_type": "lead_created",
                "name": "Denied Definition",
                "config": {"actions": [{"action_type": "log", "message": "x"}]},
            },
        )

        assert response.status_code == 403
        assert "cannot create workflow definitions" in response.json()["detail"]

    def test_create_rejects_missing_actions(self, client, owner_user: CurrentUser):
        response = client.post(
            "/api/v1/workflow-definitions",
            headers=_auth_headers(owner_user),
            json={
                "event_type": "lead_created",
                "name": "Invalid Definition",
                "config": {},
            },
        )

        assert response.status_code == 422
        assert "must contain at least one action" in str(response.json())


class TestWorkflowDefinitionRead:
    """Read/list endpoint behavior."""

    def test_staff_can_list_and_get_definitions(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
        staff_user: CurrentUser,
    ):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Readable Definition",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add(definition)
        test_db.commit()

        list_response = client.get(
            "/api/v1/workflow-definitions",
            headers=_auth_headers(staff_user),
        )
        assert list_response.status_code == 200
        list_body = list_response.json()
        assert list_body["total"] == 1
        assert list_body["items"][0]["id"] == str(definition.id)

        get_response = client.get(
            f"/api/v1/workflow-definitions/{definition.id}",
            headers=_auth_headers(staff_user),
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == str(definition.id)

    def test_list_filters_by_event_type_and_is_active(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        matching = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Matching",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        non_matching = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.TASK_CREATED,
            is_active=False,
            name="Non Matching",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add_all([matching, non_matching])
        test_db.commit()

        response = client.get(
            "/api/v1/workflow-definitions?event_type=lead_created&is_active=true",
            headers=_auth_headers(owner_user),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(matching.id)

    def test_list_enforces_max_page_size(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        for index in range(settings.max_page_size + 5):
            test_db.add(
                WorkflowDefinition(
                    id=uuid4(),
                    business_id=owner_user.business_id,
                    event_type=EventType.LEAD_CREATED,
                    is_active=True,
                    name=f"Def {index}",
                    config={"actions": [{"action_type": "log", "message": "ok"}]},
                )
            )
        test_db.commit()

        response = client.get(
            "/api/v1/workflow-definitions?limit=9999",
            headers=_auth_headers(owner_user),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == settings.max_page_size
        assert len(body["items"]) == settings.max_page_size


class TestWorkflowDefinitionUpdateDelete:
    """Patch/delete endpoint behavior."""

    def test_patch_is_active_only_skips_config_revalidation(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        # Intentionally invalid config shape persisted directly in DB.
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Broken Config Definition",
            config={"actions": [{"action_type": "log"}]},
        )
        test_db.add(definition)
        test_db.commit()

        response = client.patch(
            f"/api/v1/workflow-definitions/{definition.id}",
            headers=_auth_headers(owner_user),
            json={"is_active": False},
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_patch_reactivation_revalidates_existing_config(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=False,
            name="Broken But Disabled",
            config={"actions": [{"action_type": "log"}]},
        )
        test_db.add(definition)
        test_db.commit()

        response = client.patch(
            f"/api/v1/workflow-definitions/{definition.id}",
            headers=_auth_headers(owner_user),
            json={"is_active": True},
        )

        assert response.status_code == 422
        assert "Invalid action config at index 0" in str(response.json())

    def test_patch_invalid_config_fails_validation(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Patch Target",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add(definition)
        test_db.commit()

        response = client.patch(
            f"/api/v1/workflow-definitions/{definition.id}",
            headers=_auth_headers(owner_user),
            json={"config": {"actions": [{"action_type": "log"}]}},
        )

        assert response.status_code == 422
        assert "Invalid action config at index 0" in str(response.json())

    def test_delete_is_soft_and_excluded_from_get_list(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
    ):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Delete Target",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add(definition)
        test_db.commit()
        definition_id = definition.id

        delete_response = client.delete(
            f"/api/v1/workflow-definitions/{definition_id}",
            headers=_auth_headers(owner_user),
        )
        assert delete_response.status_code == 204

        # Soft-deleted row remains in DB with deleted_at set.
        persisted = (
            test_db.query(WorkflowDefinition)
            .filter(WorkflowDefinition.id == definition_id)
            .first()
        )
        assert persisted is not None
        assert persisted.deleted_at is not None
        assert persisted.is_active is False

        get_response = client.get(
            f"/api/v1/workflow-definitions/{definition_id}",
            headers=_auth_headers(owner_user),
        )
        assert get_response.status_code == 404

        list_response = client.get(
            "/api/v1/workflow-definitions",
            headers=_auth_headers(owner_user),
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 0


class TestWorkflowDefinitionRepository:
    """Repository guardrails for update field restrictions."""

    def test_update_definition_rejects_unknown_fields(self, test_db: Session, owner_user: CurrentUser):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Repo Guard",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add(definition)
        test_db.commit()

        repo = WorkflowDefinitionRepository(test_db)
        with pytest.raises(ValueError, match="Unsupported workflow definition update fields"):
            repo.update_definition(
                db=test_db,
                business_id=owner_user.business_id,
                definition_id=definition.id,
                conditions={"unexpected": True},
            )
