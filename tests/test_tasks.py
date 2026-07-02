"""Task tests - CRUD, RBAC, completion, multi-tenant isolation."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.task import TaskService
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.auth import CurrentUser


class TestTaskCreate:
    """Test task creation with RBAC."""

    def test_create_task_as_owner(self, test_db: Session, owner_user: CurrentUser):
        """Owner can create tasks."""
        service = TaskService(test_db)
        data = TaskCreate(
            title="Follow up with client",
            priority="high",
            status="pending",
        )

        task = service.create(owner_user.business_id, owner_user, data)

        assert task.title == "Follow up with client"
        assert task.priority == "high"
        assert task.business_id == owner_user.business_id

    def test_create_task_as_manager(self, test_db: Session, manager_user: CurrentUser):
        """Manager can create tasks."""
        service = TaskService(test_db)
        data = TaskCreate(title="Prepare proposal")

        task = service.create(manager_user.business_id, manager_user, data)

        assert task.title == "Prepare proposal"
        assert task.business_id == manager_user.business_id

    def test_create_task_as_staff_denied(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot create tasks."""
        service = TaskService(test_db)
        data = TaskCreate(title="Test task")

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)


class TestTaskRead:
    """Test task retrieval."""

    def test_get_task(self, test_db: Session, owner_user: CurrentUser, sample_task: Task):
        """Get task by ID."""
        service = TaskService(test_db)

        task = service.get(owner_user.business_id, owner_user, sample_task.id)

        assert task.id == sample_task.id
        assert task.title == sample_task.title

    def test_owner_manager_see_all_tasks(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser, sample_task: Task):
        """Owner/Manager see all tasks."""
        service = TaskService(test_db)

        # Owner sees all
        tasks, total = service.list(owner_user.business_id, owner_user)
        assert total >= 1

        # Manager sees all (in their business)
        sample_task.business_id = manager_user.business_id
        test_db.commit()
        tasks, total = service.list(manager_user.business_id, manager_user)
        assert total >= 1

    def test_staff_sees_only_assigned_tasks(self, test_db: Session, staff_user: CurrentUser):
        """Staff only sees tasks assigned to them."""
        service = TaskService(test_db)

        # Create task assigned to staff
        task1 = service.repo.create(
            business_id=staff_user.business_id,
            title="Staff task",
            assigned_to=staff_user.id,
        )
        # Create task assigned to someone else
        task2 = service.repo.create(
            business_id=staff_user.business_id,
            title="Other task",
            assigned_to=uuid4(),
        )
        test_db.commit()

        tasks, total = service.list(staff_user.business_id, staff_user)

        assert any(t.id == task1.id for t in tasks)
        assert not any(t.id == task2.id for t in tasks)


class TestTaskUpdate:
    """Test task updates."""

    def test_owner_can_update_any_task(self, test_db: Session, owner_user: CurrentUser, sample_task: Task):
        """Owner can update any task."""
        service = TaskService(test_db)
        data = TaskUpdate(status="in_progress")

        task = service.update(owner_user.business_id, owner_user, sample_task.id, data)

        assert task.status == "in_progress"

    def test_staff_can_only_update_own_task(self, test_db: Session, staff_user: CurrentUser):
        """Staff can only update tasks assigned to them."""
        service = TaskService(test_db)

        # Create task assigned to staff
        task = service.repo.create(
            business_id=staff_user.business_id,
            title="My task",
            assigned_to=staff_user.id,
        )
        test_db.commit()

        data = TaskUpdate(status="in_progress")
        updated = service.update(staff_user.business_id, staff_user, task.id, data)

        assert updated.status == "in_progress"

    def test_staff_cannot_update_unassigned_task(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot update tasks not assigned to them."""
        service = TaskService(test_db)

        # Create task assigned to someone else
        task = service.repo.create(
            business_id=staff_user.business_id,
            title="Other task",
            assigned_to=uuid4(),
        )
        test_db.commit()

        data = TaskUpdate(status="in_progress")

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, task.id, data)

    def test_completion_sets_completed_at(self, test_db: Session, owner_user: CurrentUser, sample_task: Task):
        """Marking task complete sets completed_at."""
        service = TaskService(test_db)
        data = TaskUpdate(status="completed")

        task = service.update(owner_user.business_id, owner_user, sample_task.id, data)

        assert task.status == "completed"
        assert task.completed_at is not None


class TestTaskRBAC:
    """Test task RBAC."""

    def test_only_manager_can_assign(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser, staff_user: CurrentUser, sample_task: Task):
        """Only owner/manager can assign tasks."""
        service = TaskService(test_db)

        # Owner can assign
        task = service.assign(owner_user.business_id, owner_user, sample_task.id, uuid4())
        assert task.assigned_to is not None

        # Manager can assign
        sample_task.business_id = manager_user.business_id
        test_db.commit()
        task = service.assign(manager_user.business_id, manager_user, sample_task.id, uuid4())
        assert task.assigned_to is not None

        # Staff cannot assign
        with pytest.raises(ValueError, match="Permission denied"):
            service.assign(staff_user.business_id, staff_user, sample_task.id, uuid4())

    def test_only_owner_can_delete(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser):
        """Only owner can delete tasks permanently."""
        service = TaskService(test_db)

        # Create task for owner
        task1 = service.repo.create(business_id=owner_user.business_id, title="Task 1")
        test_db.commit()

        # Owner can delete
        success = service.delete(owner_user.business_id, owner_user, task1.id)
        assert success is True

        # Manager cannot delete
        task2 = service.repo.create(business_id=manager_user.business_id, title="Task 2")
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(manager_user.business_id, manager_user, task2.id)


class TestTaskFiltering:
    """Test task status and date filtering."""

    def test_list_by_status(self, test_db: Session, owner_user: CurrentUser):
        """List tasks filtered by status."""
        service = TaskService(test_db)

        # Create tasks with different statuses
        task1 = service.repo.create(business_id=owner_user.business_id, title="Pending", status="pending")
        task2 = service.repo.create(business_id=owner_user.business_id, title="In Progress", status="in_progress")
        task3 = service.repo.create(business_id=owner_user.business_id, title="Pending 2", status="pending")
        test_db.commit()

        # List pending tasks
        tasks, total = service.list_by_status(owner_user.business_id, owner_user, "pending")

        assert total == 2
        assert all(t.status == "pending" for t in tasks)

    def test_list_overdue(self, test_db: Session, owner_user: CurrentUser):
        """List overdue tasks."""
        service = TaskService(test_db)

        # Create overdue task
        past = datetime.now(tz=None) - timedelta(days=1)
        task1 = service.repo.create(
            business_id=owner_user.business_id,
            title="Overdue",
            due_date=past,
            status="pending",
        )
        # Create future task
        future = datetime.now(tz=None) + timedelta(days=1)
        task2 = service.repo.create(
            business_id=owner_user.business_id,
            title="Future",
            due_date=future,
            status="pending",
        )
        test_db.commit()

        tasks, total = service.list_overdue(owner_user.business_id, owner_user)

        assert total >= 1
        assert any(t.id == task1.id for t in tasks)


class TestTaskMultiTenancy:
    """Test multi-tenant isolation."""

    def test_task_isolation_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        """Task from one business not visible to another."""
        service = TaskService(test_db)
        task = service.repo.create(business_id=owner_user.business_id, title="Isolated task")
        test_db.commit()

        # Owner can see their task
        retrieved = service.get(owner_user.business_id, owner_user, task.id)
        assert retrieved is not None

        # Other business cannot see it
        retrieved = service.get(other_user.business_id, other_user, task.id)
        assert retrieved is None
