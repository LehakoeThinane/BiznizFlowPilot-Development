"""Marketing CMS blog post API routes - MM Nexus's own blog CMS, every route
gated behind marketing-CMS admin auth (fully separate from tenant/platform
auth). Not tenant-scoped - there is no business_id here."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies_marketing_cms import get_current_marketing_cms_admin
from app.repositories.marketing_blog_post import MarketingBlogPostRepository
from app.schemas.marketing_cms import (
    BlogGenerateRequest,
    BlogGenerateResponse,
    BlogPostCreate,
    BlogPostListItem,
    BlogPostListResponse,
    BlogPostResponse,
    BlogPostUpdate,
    BlogPublishRequest,
    BlogPublishResponse,
    CurrentMarketingCmsAdmin,
)
from app.services import marketing_blog

router = APIRouter(prefix="/api/v1/marketing/cms/blog", tags=["marketing-cms"])


@router.get("", response_model=BlogPostListResponse)
def list_posts(
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
) -> BlogPostListResponse:
    posts = MarketingBlogPostRepository(db).list(status=status)
    return BlogPostListResponse(items=[BlogPostListItem.model_validate(p) for p in posts])


@router.post("", response_model=BlogPostResponse, status_code=201)
def create_post(
    body: BlogPostCreate,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPostResponse:
    repo = MarketingBlogPostRepository(db)
    if repo.get_by_slug(body.slug):
        raise HTTPException(status_code=400, detail="A post with this slug already exists")
    post = repo.create(
        title=body.title,
        slug=body.slug,
        description="",
        author="MM Nexus",
        content_blocks=[],
        created_by=current_admin.marketing_cms_admin_id,
        updated_by=current_admin.marketing_cms_admin_id,
    )
    return BlogPostResponse.model_validate(post)


@router.get("/{post_id}", response_model=BlogPostResponse)
def get_post(
    post_id: UUID,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPostResponse:
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return BlogPostResponse.model_validate(post)


@router.patch("/{post_id}", response_model=BlogPostResponse)
def update_post(
    post_id: UUID,
    body: BlogPostUpdate,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPostResponse:
    """Autosave target - updates whichever fields are present in the payload."""
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    post.updated_by = current_admin.marketing_cms_admin_id
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: UUID,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a draft. Published posts must not be deleted from here - the
    live site file would keep existing independently of this row, which
    would desync the CMS from what's actually published."""
    repo = MarketingBlogPostRepository(db)
    post = repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == "published":
        raise HTTPException(status_code=400, detail="Cannot delete a published post - unpublish it first")
    repo.delete(post_id)


@router.post("/{post_id}/generate", response_model=BlogGenerateResponse)
def generate_post_content(
    post_id: UUID,
    body: BlogGenerateRequest,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogGenerateResponse:
    """AI-assist: draft Markdown body content for a topic. Does not save -
    the client merges the returned Markdown into the editor for review."""
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    markdown = marketing_blog.generate_content(topic=body.topic, tone=body.tone)
    return BlogGenerateResponse(markdown=markdown)


@router.post("/{post_id}/publish", response_model=BlogPublishResponse)
def publish_post(
    post_id: UUID,
    body: BlogPublishRequest,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPublishResponse:
    """Commit the post to MM-Nexus-Website's main branch, triggering the
    site's existing deploy pipeline, and mark it published."""
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.title or not post.description:
        raise HTTPException(status_code=400, detail="Title and description are required before publishing")

    if post.status != "published":
        post.published_at = datetime.now(timezone.utc)

    try:
        commit_sha = marketing_blog.publish(post, body.markdown_body)
    except marketing_blog.MarketingBlogPublishError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    post.status = "published"
    post.github_commit_sha = commit_sha
    post.updated_by = current_admin.marketing_cms_admin_id
    db.commit()

    return BlogPublishResponse(published=True, github_commit_sha=commit_sha)
