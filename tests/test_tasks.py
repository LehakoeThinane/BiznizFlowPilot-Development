"""Task tests - CRUD, RBAC, completion, multi-tenant isolation."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import ConcurrencyConflictError
from app.core.security import hash_password
from app.models.business import Business
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.services.task import TaskService
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.auth import CurrentUser


def _second_staff_user(test_db: Session, business: Business) -> CurrentUser:
    """Create an extra staff user in the same business, for co-assignee tests."""
    user = User(
        id=uuid4(),
        business_id=business.id,
        email=f"staff2-{uuid4().hex[:8]}@test.com",
        hashed_password=hash_password("password123"),
        first_name="Second",
        last_name="Staff",
        role="staff",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return CurrentUser(
        user_id=str(user.id),
        business_id=str(business.id),
        email=user.email,
        role="staff",
        full_name=f"{user.first_name} {user.last_name}",
    )


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

    def test_create_task_as_staff_self_assigned(self, test_db: Session, staff_user: CurrentUser):
        """Staff can create tasks, but the task is assigned to themselves."""
        service = TaskService(test_db)
        data = TaskCreate(title="Test task")

        task = service.create(staff_user.business_id, staff_user, data)

        assert task.title == "Test task"
        assert task.assigned_to == staff_user.user_id

    def test_staff_cannot_assign_task_to_other_user(self, test_db: Session, staff_user: CurrentUser, manager_user: CurrentUser):
        """Staff cannot create work assigned to another user."""
        service = TaskService(test_db)
        data = TaskCreate(title="Test task", assigned_to=manager_user.user_id)

        with pytest.raises(PermissionError, match="themselves"):
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


class TestTaskConcurrency:
    """Test optimistic-concurrency protection on task updates."""

    def test_stale_update_raises_conflict(self, test_db: Session, owner_user: CurrentUser, sample_task: Task):
        """Updating a task loaded before someone else's concurrent write raises ConcurrencyConflictError."""
        service = TaskService(test_db)

        # A second, independent session simulates another request/worker that
        # loads and commits a change to the same row while our session is
        # still holding the version it originally loaded.
        OtherSession = sessionmaker(bind=test_db.get_bind())
        other_session = OtherSession()
        try:
            other_task = other_session.query(Task).filter(Task.id == sample_task.id).first()
            other_task.title = "Changed by someone else"
            other_session.commit()
        finally:
            other_session.close()

        # sample_task is still loaded in test_db's identity map at the old version.
        data = TaskUpdate(status="in_progress")
        with pytest.raises(ConcurrencyConflictError):
            service.update(owner_user.business_id, owner_user, sample_task.id, data)

    def test_stale_assign_raises_conflict(self, test_db: Session, owner_user: CurrentUser, sample_task: Task):
        """Assigning a task loaded before someone else's concurrent write raises ConcurrencyConflictError."""
        service = TaskService(test_db)

        OtherSession = sessionmaker(bind=test_db.get_bind())
        other_session = OtherSession()
        try:
            other_task = other_session.query(Task).filter(Task.id == sample_task.id).first()
            other_task.title = "Changed by someone else"
            other_session.commit()
        finally:
            other_session.close()

        with pytest.raises(ConcurrencyConflictError):
            service.assign(owner_user.business_id, owner_user, sample_task.id, uuid4())


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
        with pytest.raises(PermissionError, match="cannot"):
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

        with pytest.raises(PermissionError, match="cannot"):
            service.delete(manager_user.business_id, manager_user, task2.id)


class TestTaskMultiAssignee:
    """Test multi-person task assignment."""

    def test_create_with_multiple_assignees(self, test_db: Session, owner_user: CurrentUser, owner_business: Business):
        service = TaskService(test_db)
        staff1 = _second_staff_user(test_db, owner_business)
        staff2 = _second_staff_user(test_db, owner_business)

        task = service.create(
            owner_user.business_id, owner_user,
            TaskCreate(title="Ship the release", assignee_ids=[staff1.user_id, staff2.user_id]),
        )

        assert str(task.assigned_to) == str(staff1.user_id)
        assert {str(uid) for uid in task.assignee_ids} == {str(staff1.user_id), str(staff2.user_id)}

    def test_create_notifies_every_assignee(self, test_db: Session, owner_user: CurrentUser, owner_business: Business):
        service = TaskService(test_db)
        staff1 = _second_staff_user(test_db, owner_business)
        staff2 = _second_staff_user(test_db, owner_business)

        task = service.create(
            owner_user.business_id, owner_user,
            TaskCreate(title="Deploy to prod", assignee_ids=[staff1.user_id, staff2.user_id]),
        )

        notified_user_ids = {
            str(n.user_id)
            for n in test_db.query(Notification).filter(Notification.related_id == task.id).all()
        }
        assert notified_user_ids == {str(staff1.user_id), str(staff2.user_id)}

    def test_co_assignee_can_view_task(self, test_db: Session, owner_user: CurrentUser, owner_business: Business):
        service = TaskService(test_db)
        staff1 = _second_staff_user(test_db, owner_business)
        staff2 = _second_staff_user(test_db, owner_business)

        task = service.create(
            owner_user.business_id, owner_user,
            TaskCreate(title="Co-owned task", assignee_ids=[staff1.user_id, staff2.user_id]),
        )

        # staff2 is a co-assignee, not the primary assigned_to - must still be able to view/update
        fetched = service.get(staff2.business_id, staff2, task.id)
        assert fetched is not None
        assert fetched.id == task.id

    def test_unrelated_staff_cannot_view(self, test_db: Session, owner_user: CurrentUser, owner_business: Business, staff_user: CurrentUser):
        service = TaskService(test_db)
        staff1 = _second_staff_user(test_db, owner_business)

        task = service.create(
            owner_user.business_id, owner_user,
            TaskCreate(title="Not for you", assignee_ids=[staff1.user_id]),
        )

        with pytest.raises(ValueError, match="Permission denied"):
            service.get(staff_user.business_id, staff_user, task.id)

    def test_update_replaces_assignee_set_and_notifies_only_new(
        self, test_db: Session, owner_user: CurrentUser, owner_business: Business
    ):
        service = TaskService(test_db)
        staff1 = _second_staff_user(test_db, owner_business)
        staff2 = _second_staff_user(test_db, owner_business)
        staff3 = _second_staff_user(test_db, owner_business)

        task = service.create(
            owner_user.business_id, owner_user,
            TaskCreate(title="Reassign me", assignee_ids=[staff1.user_id, staff2.user_id]),
        )

        updated = service.update(
            owner_user.business_id, owner_user, task.id,
            TaskUpdate(assignee_ids=[staff2.user_id, staff3.user_id]),
        )

        assert {str(uid) for uid in updated.assignee_ids} == {str(staff2.user_id), str(staff3.user_id)}

        # Only staff3 is newly added - staff2 was already an assignee and shouldn't be re-notified
        all_notifications = test_db.query(Notification).filter(
            Notification.related_id == task.id, Notification.title == "New task assigned"
        ).all()
        staff2_notification_count = sum(1 for n in all_notifications if str(n.user_id) == str(staff2.user_id))
        staff3_notification_count = sum(1 for n in all_notifications if str(n.user_id) == str(staff3.user_id))
        assert staff2_notification_count == 1  # only from the original create, not re-notified on update
        assert staff3_notification_count == 1


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


class TestTaskResponseOverdue:
    """TaskResponse recomputes status="overdue" at read time from due_date.

    The DB column only ever holds pending/in_progress/completed - nothing
    writes "overdue" onto the row. Every response (board, list, get-by-id)
    goes through TaskResponse, so this is the single place that has to get
    it right for the whole app to agree.
    """

    def test_past_due_pending_task_reports_overdue(self, test_db: Session, owner_user: CurrentUser):
        from app.schemas.task import TaskResponse

        service = TaskService(test_db)
        past = datetime.now(tz=None) - timedelta(days=1)
        task = service.repo.create(
            business_id=owner_user.business_id, title="Late", due_date=past, status="pending",
        )
        test_db.commit()

        assert TaskResponse.model_validate(task).status == "overdue"

    def test_past_due_completed_task_stays_completed(self, test_db: Session, owner_user: CurrentUser):
        from app.schemas.task import TaskResponse

        service = TaskService(test_db)
        past = datetime.now(tz=None) - timedelta(days=1)
        task = service.repo.create(
            business_id=owner_user.business_id, title="Done late", due_date=past, status="completed",
        )
        test_db.commit()

        assert TaskResponse.model_validate(task).status == "completed"

    def test_future_due_task_not_overdue(self, test_db: Session, owner_user: CurrentUser):
        from app.schemas.task import TaskResponse

        service = TaskService(test_db)
        future = datetime.now(tz=None) + timedelta(days=1)
        task = service.repo.create(
            business_id=owner_user.business_id, title="Not yet", due_date=future, status="pending",
        )
        test_db.commit()

        assert TaskResponse.model_validate(task).status == "pending"

    def test_api_status_filter_overdue_returns_past_due_tasks(
        self, client, test_db: Session, registered_user,
    ):
        """The "Overdue" option in the status filter dropdown queries by
        due_date under the hood now, not a literal (never-written) DB value.
        """
        headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
        past = (datetime.now(tz=None) - timedelta(days=1)).isoformat()

        create_resp = client.post(
            "/api/v1/tasks",
            json={"title": "Overdue via API", "due_date": past, "status": "pending"},
            headers=headers,
        )
        assert create_resp.status_code == 200, create_resp.text

        list_resp = client.get("/api/v1/tasks?status=overdue", headers=headers)
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert any(t["title"] == "Overdue via API" and t["status"] == "overdue" for t in body["items"])


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
