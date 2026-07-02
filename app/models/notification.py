"""In-app notification model."""

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM

from app.models.base import BaseModel

_notif_type = ENUM(
    "low_stock", "overdue_task", "order_status", "payroll", "leave", "system",
    name="notification_type", create_type=False,
)


class Notification(BaseModel):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_business", "business_id"),
    )

    business_id   = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id       = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type          = Column(_notif_type, nullable=False)
    title         = Column(String(200), nullable=False)
    message       = Column(Text, nullable=False)
    is_read       = Column(Boolean, nullable=False, default=False, server_default="false")
    action_url    = Column(String(300), nullable=True)
    related_type  = Column(String(50), nullable=True)
    related_id    = Column(Uuid, nullable=True)
