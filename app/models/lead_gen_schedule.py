"""LeadGenSchedule model - a saved Google Places search that the scheduled
lead-gen task re-runs automatically (Mon/Wed/Thu), instead of a human having
to trigger POST /api/v1/leads/find by hand every time."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text, Uuid

from app.models.base import BaseModel


class LeadGenSchedule(BaseModel):
    """One recurring Google Places search for a business."""

    __tablename__ = "lead_gen_schedules"

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )

    query = Column(
        Text,
        nullable=False,
        doc='Google Places text search, e.g. "hardware stores in Johannesburg"',
    )

    max_results = Column(
        Integer,
        nullable=False,
        default=15,
        server_default="15",
        doc="Cap per scheduled run - keeps API spend bounded",
    )

    active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Inactive schedules are kept (for history) but skipped by the scheduled run",
    )

    def __repr__(self) -> str:
        return f"<LeadGenSchedule id={self.id} query='{self.query}' active={self.active}>"
