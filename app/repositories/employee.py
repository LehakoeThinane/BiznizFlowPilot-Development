"""Employee repository - data access for Employee model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.hr import Employee
from app.repositories.base import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    """Employee repository with multi-tenant filtering."""

    def __init__(self, db: Session):
        """Initialize with Employee model."""
        super().__init__(db, Employee)

    def find_unlinked_by_email(self, business_id: UUID, email: str) -> Optional[Employee]:
        """Find a still-unlinked Employee in this business with a matching
        email - used to auto-link an accepted invite to a pre-existing HR
        record.

        🧨 CRITICAL: Filters by business_id

        Args:
            business_id: Tenant ID
            email: Email to match, case-insensitively

        Returns:
            Employee or None
        """
        return self.db.query(Employee).filter(
            Employee.business_id == business_id,  # 🧨 MULTI-TENANCY
            Employee.user_id.is_(None),
            func.lower(Employee.email) == email.lower(),
        ).first()

    def find_linked_to_user(
        self, business_id: UUID, user_id: UUID, exclude_employee_id: Optional[UUID] = None
    ) -> Optional[Employee]:
        """Find the active Employee (if any) already linked to this user_id.

        🧨 CRITICAL: Filters by business_id

        Args:
            business_id: Tenant ID
            user_id: User ID to check for an existing link
            exclude_employee_id: Skip this employee (used when checking a
                link change on the employee being updated, not created)

        Returns:
            Employee or None
        """
        q = self.db.query(Employee).filter(
            Employee.business_id == business_id,  # 🧨 MULTI-TENANCY
            Employee.user_id == user_id,
            Employee.is_active.is_(True),
        )
        if exclude_employee_id:
            q = q.filter(Employee.id != exclude_employee_id)
        return q.first()
