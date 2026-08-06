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
from app.repositories.marketing_blog_topic import MarketingBlogTopicRepository
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
    BlogScheduleAutoPublishRequest,
    BlogTopicCreate,
    BlogTopicListResponse,
    BlogTopicResponse,
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


@router.get("/topics", response_model=BlogTopicListResponse)
def list_blog_topics(
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogTopicListResponse:
    """The autopublish task's topic backlog - listed so the admin UI can
    show what's queued and what's already been used."""
    topics = MarketingBlogTopicRepository(db).list()
    return BlogTopicListResponse(items=[BlogTopicResponse.model_validate(t) for t in topics])


@router.post("/topics", response_model=BlogTopicResponse, status_code=201)
def create_blog_topic(
    body: BlogTopicCreate,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogTopicResponse:
    topic = MarketingBlogTopicRepository(db).create(topic=body.topic, tone=body.tone)
    return BlogTopicResponse.model_validate(topic)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_blog_topic(
    topic_id: UUID,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    found = MarketingBlogTopicRepository(db).delete(topic_id)
    if not found:
        raise HTTPException(status_code=404, detail="Topic not found")


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


@router.patch("/{post_id}/schedule-auto-publish", response_model=BlogPostResponse)
def schedule_post_auto_publish(
    post_id: UUID,
    body: BlogScheduleAutoPublishRequest,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPostResponse:
    """Queue a draft for the daily autopublish task - stores the
    client-computed markdown snapshot the task will publish, since it has
    no browser/BlockNote available to compute it itself."""
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.title or not post.description:
        raise HTTPException(status_code=400, detail="Title and description are required before scheduling")

    post.auto_publish_ready = True
    post.pending_markdown_body = body.markdown_body
    post.updated_by = current_admin.marketing_cms_admin_id
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)


@router.post("/{post_id}/cancel-auto-publish", response_model=BlogPostResponse)
def cancel_post_auto_publish(
    post_id: UUID,
    current_admin: Annotated[CurrentMarketingCmsAdmin, Depends(get_current_marketing_cms_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> BlogPostResponse:
    post = MarketingBlogPostRepository(db).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.auto_publish_ready = False
    post.updated_by = current_admin.marketing_cms_admin_id
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)
