"""MarketingBlogTopic repository - data access for the daily autopublish
task's topic backlog. Not a BaseRepository subclass - no business_id
scoping, same convention as MarketingBlogPostRepository."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.marketing_blog_topic import MarketingBlogTopic


class MarketingBlogTopicRepository:
    """Marketing blog topic repository."""

    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[MarketingBlogTopic]:
        """List all topics, oldest first."""
        return self.db.query(MarketingBlogTopic).order_by(MarketingBlogTopic.created_at.asc()).all()

    def create(self, **fields) -> MarketingBlogTopic:
        topic = MarketingBlogTopic(**fields)
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def delete(self, topic_id: UUID) -> bool:
        topic = self.db.query(MarketingBlogTopic).filter(MarketingBlogTopic.id == topic_id).first()
        if not topic:
            return False
        self.db.delete(topic)
        self.db.commit()
        return True

    def get_next_unused(self) -> Optional[MarketingBlogTopic]:
        """The oldest topic not yet consumed by the autopublish task."""
        return (
            self.db.query(MarketingBlogTopic)
            .filter(MarketingBlogTopic.used_at.is_(None))
            .order_by(MarketingBlogTopic.created_at.asc())
            .first()
        )

    def mark_used(self, topic: MarketingBlogTopic) -> None:
        topic.used_at = datetime.now(timezone.utc)
        self.db.commit()
