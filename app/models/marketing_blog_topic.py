"""MarketingBlogTopic model - a backlog of article topics the daily
autopublish task draws from when no human-written draft is ready to
publish. FIFO: the oldest unused topic (used_at IS NULL) goes next."""

from sqlalchemy import Column, DateTime, String, Text

from app.models.base import BaseModel


class MarketingBlogTopic(BaseModel):
    """One queued topic for AI-generated blog content."""

    __tablename__ = "marketing_blog_topics"

    topic = Column(Text, nullable=False)
    tone = Column(String(100), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<MarketingBlogTopic id={self.id} used={self.used_at is not None}>"
