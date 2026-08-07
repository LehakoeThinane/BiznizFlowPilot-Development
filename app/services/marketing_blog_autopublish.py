"""Daily blog autopublish decision logic - the connective tissue between
the existing marketing blog CMS (app/services/marketing_blog.py) and a
Celery beat schedule (app/workers/marketing_blog_autopublish.py).

Priority each run: a human-scheduled draft always wins over generating one,
since a human already decided its content is ready. Only when nothing is
scheduled does this fall back to the AI topic queue - and even then, it
refuses to publish if AI_PROVIDER was never configured (still "echo"),
rather than shipping placeholder text to the live site. Every branch sends
exactly one staff notification so the automation is never silent, whether
it published, skipped, or failed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.image_gen import ImageGenError
from app.models.marketing_blog_post import MarketingBlogPost
from app.models.marketing_blog_topic import MarketingBlogTopic
from app.repositories.marketing_blog_post import MarketingBlogPostRepository
from app.repositories.marketing_blog_topic import MarketingBlogTopicRepository
from app.services import email, marketing_blog


def run_daily_autopublish(db: Session) -> dict[str, str]:
    """Entry point for the daily Celery task. Returns a small outcome dict
    for logging - never raises on a normal skip/failure, only on genuinely
    unexpected errors (e.g. a DB failure), matching this codebase's other
    periodic-task services."""
    if not settings.marketing_blog_autopublish_enabled:
        return {"outcome": "disabled"}

    post_repo = MarketingBlogPostRepository(db)
    topic_repo = MarketingBlogTopicRepository(db)

    last_published = post_repo.get_last_published()
    if last_published and last_published.published_at:
        if last_published.published_at.astimezone(timezone.utc).date() == datetime.now(timezone.utc).date():
            return {"outcome": "already_published_today"}

    scheduled = post_repo.get_next_auto_publish_ready()
    if scheduled is not None:
        return _publish_scheduled_post(db, scheduled)

    topic = topic_repo.get_next_unused()
    if topic is None:
        email.send_blog_autopublish_notice(
            "skipped", "No topics queued and no drafts scheduled - add a topic in the blog admin."
        )
        return {"outcome": "no_topic_available"}

    if settings.ai_provider == "echo":
        email.send_blog_autopublish_notice(
            "skipped",
            "AI_PROVIDER is not configured (still 'echo') - set a real provider before "
            "autopublish can generate content. The queued topic was left untouched.",
        )
        return {"outcome": "ai_not_configured"}

    return _generate_and_publish_from_topic(db, topic_repo, topic)


def _publish_scheduled_post(db: Session, post: MarketingBlogPost) -> dict[str, str]:
    markdown_body = post.pending_markdown_body or ""
    post.published_at = datetime.now(timezone.utc)
    try:
        commit_sha, linkedin_status = marketing_blog.publish_and_cross_post(post, markdown_body)
    except marketing_blog.MarketingBlogPublishError as e:
        db.rollback()
        email.send_blog_autopublish_notice(
            "failed", f"Failed to publish scheduled post '{post.title}': {e}", post_id=str(post.id)
        )
        return {"outcome": "failed", "post_id": str(post.id)}

    post.status = "published"
    post.github_commit_sha = commit_sha
    post.auto_publish_ready = False
    post.pending_markdown_body = None
    db.commit()
    email.send_blog_autopublish_notice(
        "published", f"Published scheduled post: {post.title} (LinkedIn: {linkedin_status})", post_id=str(post.id)
    )
    return {"outcome": "published", "post_id": str(post.id)}


def _generate_and_publish_from_topic(
    db: Session, topic_repo: MarketingBlogTopicRepository, topic: MarketingBlogTopic
) -> dict[str, str]:
    draft = marketing_blog.generate_full_post(topic.topic, topic.tone)
    slug = marketing_blog.unique_slug(db, draft.title)

    post = MarketingBlogPostRepository(db).create(
        slug=slug,
        title=draft.title,
        description=draft.description,
        author="MM Nexus",
        content_blocks=[],
        pending_markdown_body=draft.markdown_body,
    )
    topic_repo.mark_used(topic)

    # Best-effort, non-blocking - a broken/unconfigured image API must never
    # stop the actual article from publishing, same "secondary action"
    # reasoning as the LinkedIn cross-post below.
    cover_image_status = "not configured"
    try:
        marketing_blog.generate_and_attach_cover_image(post)
        cover_image_status = "generated"
    except ImageGenError:
        pass
    except marketing_blog.MarketingBlogPublishError as e:
        cover_image_status = f"failed: {e}"

    if settings.marketing_blog_autopublish_requires_approval:
        email.send_blog_autopublish_notice(
            "needs review", f"AI-generated post ready for review: {draft.title}", post_id=str(post.id)
        )
        return {"outcome": "needs_review", "post_id": str(post.id)}

    post.published_at = datetime.now(timezone.utc)
    try:
        commit_sha, linkedin_status = marketing_blog.publish_and_cross_post(post, draft.markdown_body)
    except marketing_blog.MarketingBlogPublishError as e:
        db.rollback()
        email.send_blog_autopublish_notice(
            "failed", f"Generated post but failed to publish '{draft.title}': {e}", post_id=str(post.id)
        )
        return {"outcome": "failed", "post_id": str(post.id)}

    post.status = "published"
    post.github_commit_sha = commit_sha
    db.commit()
    email.send_blog_autopublish_notice(
        "published",
        f"Published AI-generated post: {draft.title} (LinkedIn: {linkedin_status}, cover image: {cover_image_status})",
        post_id=str(post.id),
    )
    return {"outcome": "published", "post_id": str(post.id)}
