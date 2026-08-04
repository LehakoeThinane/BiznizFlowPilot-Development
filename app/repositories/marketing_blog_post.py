"""MarketingBlogPost repository - data access for MM Nexus's own marketing
blog CMS content. Not a BaseRepository subclass - no business_id scoping."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.marketing_blog_post import MarketingBlogPost


class MarketingBlogPostRepository:
    """Marketing blog post repository."""

    def __init__(self, db: Session):
        """Initialize with a DB session."""
        self.db = db

    def list(self, status: Optional[str] = None) -> list[MarketingBlogPost]:
        """List posts, newest first, optionally filtered by status."""
        query = self.db.query(MarketingBlogPost)
        if status:
            query = query.filter(MarketingBlogPost.status == status)
        return query.order_by(MarketingBlogPost.updated_at.desc()).all()

    def get_by_id(self, post_id: UUID) -> Optional[MarketingBlogPost]:
        """Look up a post by ID."""
        return self.db.query(MarketingBlogPost).filter(MarketingBlogPost.id == post_id).first()

    def get_by_slug(self, slug: str) -> Optional[MarketingBlogPost]:
        """Look up a post by slug."""
        return self.db.query(MarketingBlogPost).filter(MarketingBlogPost.slug == slug).first()

    def create(self, **fields) -> MarketingBlogPost:
        """Create a new draft post."""
        post = MarketingBlogPost(**fields)
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete(self, post_id: UUID) -> bool:
        """Delete a post by ID. Returns False if it didn't exist."""
        post = self.get_by_id(post_id)
        if not post:
            return False
        self.db.delete(post)
        self.db.commit()
        return True
