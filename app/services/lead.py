"""Lead service - business logic with auto-event emission."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.lead import Lead
from app.repositories.lead import LeadRepository
from app.schemas.lead import LeadCreate, LeadUpdate
from app.schemas.auth import CurrentUser


class LeadService:
    """Lead service with RBAC and pipeline state management.
    
    🧨 RBAC: Owner/Manager can create/assign. Staff can view own and update status.
    State transitions: new → contacted → qualified → (won|lost)
    
    Auto-emits events on create/update/delete when event_service is provided.
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        "new": ["contacted", "lost"],
        "contacted": ["qualified", "lost"],
        "qualified": ["won", "lost"],
        "won": [],
        "lost": [],
    }

    def __init__(self, db: Session, event_service=None):
        """Initialize service.
        
        Args:
            db: SQLAlchemy session
            event_service: Optional EventService for auto-event emission.
                           When None, no events are emitted (backward compatible).
        """
        self.db = db
        self.repo = LeadRepository(db)
        self._event_service = event_service

    def _emit_event(
        self,
        event_type: EventType,
        business_id: UUID,
        entity_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Queue an event row in the same (not-yet-committed) transaction as
        the caller's pending business-row change - the caller commits once,
        after this call, so both persist atomically or neither does."""
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id,
            event_type=event_type,
            entity_type="lead",
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            data=data,
            commit=False,
        )

    def create(self, business_id: UUID, current_user: CurrentUser, data: LeadCreate) -> Lead:
        """Create lead.
        
        🧨 RBAC: Only owner/manager can create.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can create leads")

        lead = self.repo.create(business_id=business_id, commit=False, **data.model_dump())

        self._emit_event(
            event_type=EventType.LEAD_CREATED,
            business_id=business_id,
            entity_id=lead.id,
            actor_id=current_user.user_id,
            description=f"Lead created with status '{lead.status}'",
            data={"status": lead.status, "source": lead.source},
        )

        self.db.commit()
        self.db.refresh(lead)
        return lead

    def get(self, business_id: UUID, current_user: CurrentUser, lead_id: UUID) -> Lead | None:
        """Get lead by ID.
        
        🧨 RBAC: All roles can view leads in their business.
        """
        return self.repo.get(business_id=business_id, entity_id=lead_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Lead], int]:
        """List leads.
        
        🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
        """
        if current_user.role in ["owner", "manager"]:
            leads = self.repo.list(business_id=business_id, skip=skip, limit=limit)
            total = self.repo.count(business_id=business_id)
        else:
            # Staff only sees leads assigned to them
            leads = self.repo.get_assigned_to(business_id=business_id, assigned_to=current_user.id, skip=skip, limit=limit)
            total = self.repo.count_assigned_to(business_id=business_id, assigned_to=current_user.id)

        return leads, total

    def list_by_status(self, business_id: UUID, current_user: CurrentUser, status: str, skip: int = 0, limit: int = 100) -> tuple[list[Lead], int]:
        """List leads by status.
        
        🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
        """
        if current_user.role in ["owner", "manager"]:
            leads = self.repo.get_by_status(business_id=business_id, status=status, skip=skip, limit=limit)
            total = self.repo.count_by_status(business_id=business_id, status=status)
        else:
            # Staff only sees own leads
            all_leads = self.repo.get_assigned_to(business_id=business_id, assigned_to=current_user.id)
            leads = [lead for lead in all_leads if lead.status == status][skip:skip+limit]
            total = len([lead for lead in all_leads if lead.status == status])

        return leads, total

    def update(self, business_id: UUID, current_user: CurrentUser, lead_id: UUID, data: LeadUpdate) -> Lead | None:
        """Update lead.
        
        🧨 RBAC: Owner/Manager can edit all. Staff can only update status of own leads.
        """
        lead = self.repo.get(business_id=business_id, entity_id=lead_id)
        if not lead:
            return None

        # Staff can only update their own leads
        if current_user.role == "staff" and lead.assigned_to != current_user.id:
            raise ValueError("Permission denied: Staff can only update their own leads")

        old_status = lead.status

        # Validate state transition if status is being updated
        if data.status is not None and data.status != lead.status:
            if not self._is_valid_transition(lead.status, data.status):
                raise ValueError(f"Invalid state transition: {lead.status} → {data.status}")

        update_data = data.model_dump(exclude_unset=True)
        updated_lead = self.repo.update(business_id=business_id, entity_id=lead_id, commit=False, **update_data)

        if updated_lead:
            # Determine the most specific event type
            if data.status is not None and data.status != old_status:
                self._emit_event(
                    event_type=EventType.LEAD_STATUS_CHANGED,
                    business_id=business_id,
                    entity_id=lead_id,
                    actor_id=current_user.user_id,
                    description=f"Lead status changed: {old_status} → {data.status}",
                    data={"old_status": old_status, "new_status": data.status},
                )
            else:
                self._emit_event(
                    event_type=EventType.LEAD_UPDATED,
                    business_id=business_id,
                    entity_id=lead_id,
                    actor_id=current_user.user_id,
                    description="Lead updated",
                    data={"updated_fields": list(update_data.keys())},
                )
            self.db.commit()
            self.db.refresh(updated_lead)

        return updated_lead

    def assign(self, business_id: UUID, current_user: CurrentUser, lead_id: UUID, assigned_to: UUID) -> Lead | None:
        """Assign lead to user.
        
        🧨 RBAC: Only owner/manager can assign.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can assign leads")

        lead = self.repo.get(business_id=business_id, entity_id=lead_id)
        if not lead:
            return None

        old_assigned = lead.assigned_to
        updated_lead = self.repo.update(business_id=business_id, entity_id=lead_id, commit=False, assigned_to=assigned_to)

        if updated_lead:
            self._emit_event(
                event_type=EventType.LEAD_ASSIGNED,
                business_id=business_id,
                entity_id=lead_id,
                actor_id=current_user.user_id,
                description=f"Lead assigned to {assigned_to}",
                data={
                    "old_assigned_to": str(old_assigned) if old_assigned else None,
                    "new_assigned_to": str(assigned_to),
                },
            )
            self.db.commit()
            self.db.refresh(updated_lead)

        return updated_lead

    def delete(self, business_id: UUID, current_user: CurrentUser, lead_id: UUID) -> bool:
        """Delete lead.
        
        🧨 RBAC: Only owner can permanently delete.
        """
        if current_user.role != "owner":
            raise ValueError("Permission denied: Only owner can delete leads")

        lead = self.repo.get(business_id=business_id, entity_id=lead_id)
        if not lead:
            return False

        # Emit event before deletion (entity still exists for context) - same
        # transaction as the delete itself, committed together below.
        self._emit_event(
            event_type=EventType.LEAD_DELETED,
            business_id=business_id,
            entity_id=lead_id,
            actor_id=current_user.user_id,
            description=f"Lead deleted (was status='{lead.status}')",
            data={"status": lead.status, "source": lead.source},
        )

        self.repo.delete(business_id=business_id, entity_id=lead_id, commit=False)
        self.db.commit()
        return True

    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Check if state transition is valid."""
        return new_status in LeadService.VALID_TRANSITIONS.get(current_status, [])
