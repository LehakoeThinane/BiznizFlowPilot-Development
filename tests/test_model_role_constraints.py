"""users.role and platform_admins.platform_role are enforced at the
database level (ck_users_role_valid / ck_platform_admins_platform_role_valid)
- RBAC throughout the app is a Python string comparison with no other
backstop, so an invalid value here would silently bypass every check."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.business import Business
from app.models.platform_admin import PlatformAdmin
from app.models.user import User


class TestUserRoleConstraint:
    @pytest.mark.parametrize("role", ["owner", "manager", "staff", "it_admin"])
    def test_valid_roles_accepted(self, test_db: Session, owner_business: Business, role: str):
        user = User(
            id=uuid4(), business_id=owner_business.id, email=f"{role}@test.com",
            hashed_password=hash_password("x"), first_name="A", last_name="B",
            role=role, is_active=True,
        )
        test_db.add(user)
        test_db.commit()  # must not raise

    def test_invalid_role_rejected(self, test_db: Session, owner_business: Business):
        user = User(
            id=uuid4(), business_id=owner_business.id, email="bad@test.com",
            hashed_password=hash_password("x"), first_name="A", last_name="B",
            role="superhacker", is_active=True,
        )
        test_db.add(user)
        with pytest.raises(IntegrityError):
            test_db.commit()


class TestPlatformAdminRoleConstraint:
    @pytest.mark.parametrize("role", ["support", "billing_ops", "admin", "super_admin"])
    def test_valid_roles_accepted(self, test_db: Session, role: str):
        admin = PlatformAdmin(
            id=uuid4(), email=f"{role}@platform.test", hashed_password=hash_password("x"),
            full_name="Admin", platform_role=role, is_active=True,
        )
        test_db.add(admin)
        test_db.commit()  # must not raise

    def test_invalid_role_rejected(self, test_db: Session):
        admin = PlatformAdmin(
            id=uuid4(), email="bad@platform.test", hashed_password=hash_password("x"),
            full_name="Admin", platform_role="root", is_active=True,
        )
        test_db.add(admin)
        with pytest.raises(IntegrityError):
            test_db.commit()
