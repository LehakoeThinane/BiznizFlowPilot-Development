"""API tests for user listing endpoint used by task assignee dropdowns."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.user import User
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


class TestUsersApi:
    """Behavioral tests for /api/v1/users."""

    def test_list_users_scopes_to_active_current_tenant(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
        owner_business: Business,
        other_business: Business,
    ):
        # Active users in owner tenant should be returned.
        owner_active_one = User(
            id=uuid4(),
            business_id=owner_business.id,
            email="alice@example.com",
            hashed_password=hash_password("password123"),
            first_name="Alice",
            last_name="Zephyr",
            role="manager",
            is_active=True,
        )
        owner_active_two = User(
            id=uuid4(),
            business_id=owner_business.id,
            email="bob@example.com",
            hashed_password=hash_password("password123"),
            first_name="Bob",
            last_name="Yellow",
            role="staff",
            is_active=True,
        )
        # Inactive users should be excluded.
        owner_inactive = User(
            id=uuid4(),
            business_id=owner_business.id,
            email="inactive@example.com",
            hashed_password=hash_password("password123"),
            first_name="Inactive",
            last_name="User",
            role="staff",
            is_active=False,
        )
        # Other-tenant users should be excluded.
        other_tenant_user = User(
            id=uuid4(),
            business_id=other_business.id,
            email="other@example.com",
            hashed_password=hash_password("password123"),
            first_name="Other",
            last_name="Tenant",
            role="owner",
            is_active=True,
        )

        test_db.add_all([owner_active_one, owner_active_two, owner_inactive, other_tenant_user])
        test_db.commit()
        owner_active_one_id = str(owner_active_one.id)
        owner_active_two_id = str(owner_active_two.id)
        owner_inactive_id = str(owner_inactive.id)
        other_tenant_user_id = str(other_tenant_user.id)

        response = client.get("/api/v1/users", headers=_auth_headers(owner_user))

        assert response.status_code == 200
        body = response.json()

        returned_ids = {item["id"] for item in body["items"]}

        # owner_user fixture creates one active owner user; include it in expected total.
        assert body["total"] == 3
        assert owner_active_one_id in returned_ids
        assert owner_active_two_id in returned_ids
        assert owner_inactive_id not in returned_ids
        assert other_tenant_user_id not in returned_ids

    def test_list_users_applies_max_page_size(
        self,
        client,
        test_db: Session,
        owner_user: CurrentUser,
        owner_business: Business,
    ):
        for index in range(settings.max_page_size + 5):
            test_db.add(
                User(
                    id=uuid4(),
                    business_id=owner_business.id,
                    email=f"user{index}@example.com",
                    hashed_password=hash_password("password123"),
                    first_name=f"User{index}",
                    last_name="Tenant",
                    role="staff",
                    is_active=True,
                )
            )
        test_db.commit()

        response = client.get(
            "/api/v1/users?skip=0&limit=9999",
            headers=_auth_headers(owner_user),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == settings.max_page_size + 6  # +5 inserted +1 owner_user fixture
        assert len(body["items"]) == settings.max_page_size

    def test_list_users_requires_authentication(self, client):
        response = client.get("/api/v1/users")
        assert response.status_code == 401
