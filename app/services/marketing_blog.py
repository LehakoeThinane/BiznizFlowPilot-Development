"""Marketing blog CMS service - AI-assisted drafting and the GitHub-backed
publish mechanism.

Publishing writes a Markdown file matching MM-Nexus-Website's existing
content collection schema exactly (title/description/publishedDate/author)
via GitHub's Contents API, committed straight to `main` - the site's
existing deploy.yml already rebuilds and FTP-deploys on any push there, so
no changes are needed to the site's own rendering or deploy pipeline.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy.orm import Session

from app.ai.engine import get_engine
from app.core.config import settings
from app.integrations import image_gen, linkedin
from app.models.marketing_blog_post import MarketingBlogPost
from app.repositories.marketing_blog_post import MarketingBlogPostRepository

_MM_NEXUS_GROUNDING = """MM Nexus's actual active services, to draw on and stay grounded in - never \
invent services that aren't listed here:

Divisions:
- AI Consulting - architecting the decision systems around AI so a team \
scales judgment instead of headcount
- Software Solutions - designing and building custom applications for \
business operations that have outgrown manual processes

Services:
- Systems Architecture - eliminating guesswork in scaling by designing \
systems around actual business operations
- Process Automation - removing manual data entry, reconciliation, and \
handoffs that consume team time
- AI Integration - automating repetitive analytical decision-making
- Custom Applications - purpose-built software replacing generic \
off-the-shelf dependency, including custom websites and web applications

Products:
- BiznizFlowPilot (live SaaS) - a CRM + ERP platform with AI lead \
qualification, tasks, inventory, finance, workflow automation, HR, and team \
chat, all in one system instead of six disconnected tools
- LendFlow - a marketplace platform connecting lenders and borrowers
- SEO-GEO Agent - an AI agent automating SEO tasks
- PaySlip-OnCheck - a PWA helping employees understand their payslips
- Financial Calculator - a PWA for calculating taxes, bonds, and financial \
commitments

Tone: direct, honest, a little conversational - like a knowledgeable person \
talking to a business owner, not corporate marketing-speak. Ground claims in \
concrete, relatable operational pain points rather than vague benefits."""

_SYSTEM_PROMPT = f"""You are a senior digital marketing copywriter for MM Nexus, a \
systems engineering consultancy. Write a complete, ready-to-publish blog post \
body in Markdown (do not include frontmatter or a title heading - the title \
is handled separately). Use ## and ### for section headings.

{_MM_NEXUS_GROUNDING}"""

_FULL_POST_SYSTEM_PROMPT = f"""You are a senior digital marketing copywriter for MM Nexus, a \
systems engineering consultancy, writing a complete blog post with no human editor involved \
before publishing - the title and description you write are what actually ships.

Respond in EXACTLY this format, nothing before or after it:

TITLE: <a concise, compelling title, no quotes around it>
DESCRIPTION: <a one-sentence meta description, under 160 characters>

<the full post body in Markdown, using ## and ### for section headings - do not repeat the \
title as a heading, it's already handled above>

{_MM_NEXUS_GROUNDING}"""


@dataclass(slots=True)
class FullPostDraft:
    """A complete AI-generated post: title, description, and Markdown body."""

    title: str
    description: str
    markdown_body: str


def generate_content(topic: str, tone: str | None = None) -> str:
    """Generate a Markdown blog post body for a topic. Returns raw Markdown -
    the caller parses it into editable blocks; nothing is saved here."""
    engine = get_engine()
    user_message = f"Topic: {topic}"
    if tone:
        user_message += f"\nTone: {tone}"
    response = engine.chat(messages=[{"role": "user", "content": user_message}], system_prompt=_SYSTEM_PROMPT)
    return response.reply


_TITLE_LINE_RE = re.compile(r"^TITLE:\s*(.+)$", re.MULTILINE)
_DESCRIPTION_LINE_RE = re.compile(r"^DESCRIPTION:\s*(.+)$", re.MULTILINE)


def _parse_full_post(raw: str, topic_fallback: str) -> FullPostDraft:
    """Parse the TITLE:/DESCRIPTION:-prefixed format _FULL_POST_SYSTEM_PROMPT
    asks for. Falls back to the topic text as the title and a truncated
    excerpt of the body as the description if the model didn't follow the
    format exactly - not every engine backend supports structured output
    reliably (see app/ai/engine.py's docstring: only Groq has tool-calling),
    so this always produces a usable post rather than raising."""
    title_match = _TITLE_LINE_RE.search(raw)
    description_match = _DESCRIPTION_LINE_RE.search(raw)

    # Strip the TITLE:/DESCRIPTION: lines themselves out of the body, however
    # many of them matched, then trim leading blank lines left behind.
    body = _TITLE_LINE_RE.sub("", raw, count=1)
    body = _DESCRIPTION_LINE_RE.sub("", body, count=1)
    body = body.lstrip("\n ")

    title = title_match.group(1).strip() if title_match else topic_fallback
    if description_match:
        description = description_match.group(1).strip()
    else:
        excerpt = re.sub(r"\s+", " ", body).strip()
        description = (excerpt[:157] + "...") if len(excerpt) > 160 else excerpt

    return FullPostDraft(title=title, description=description, markdown_body=body.strip())


def generate_full_post(topic: str, tone: str | None = None) -> FullPostDraft:
    """Generate a complete post (title + description + Markdown body) for the
    daily autopublish task - unlike generate_content(), no human picks a
    title afterward, so the model has to produce one."""
    engine = get_engine()
    user_message = f"Topic: {topic}"
    if tone:
        user_message += f"\nTone: {tone}"
    response = engine.chat(messages=[{"role": "user", "content": user_message}], system_prompt=_FULL_POST_SYSTEM_PROMPT)
    return _parse_full_post(response.reply, topic_fallback=topic)


def _slugify(title: str) -> str:
    """Python port of MM-Nexus-Website's BlogAdminList.tsx slugify() - lowercase,
    collapse runs of non-alphanumeric characters into a single hyphen, trim
    edge hyphens."""
    lowered = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-")


def unique_slug(db: Session, title: str) -> str:
    """A slug guaranteed free in marketing_blog_posts - appends -2, -3, ...
    if the plain slugified title is already taken."""
    repo = MarketingBlogPostRepository(db)
    base = _slugify(title) or "post"
    slug = base
    suffix = 2
    while repo.get_by_slug(slug):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _yaml_quote(value: str) -> str:
    """Minimal double-quoted YAML scalar escaping - sufficient for the plain
    title/description/author strings this frontmatter ever holds. Not a
    general YAML escaper; avoids pulling in PyYAML for four fixed fields."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_markdown_file(post: MarketingBlogPost, markdown_body: str) -> str:
    published_date = (post.published_at.date() if post.published_at else date.today()).isoformat()
    frontmatter = (
        "---\n"
        f"title: {_yaml_quote(post.title)}\n"
        f"description: {_yaml_quote(post.description)}\n"
        + (f"coverImage: {_yaml_quote(post.cover_image_url)}\n" if post.cover_image_url else "")
        + f"publishedDate: {published_date}\n"
        f"author: {_yaml_quote(post.author)}\n"
        "---\n"
    )
    return f"{frontmatter}\n{markdown_body.strip()}\n"


class MarketingBlogPublishError(Exception):
    """Raised when the GitHub Contents API publish step fails."""


def _commit_file_to_github(path: str, content_bytes: bytes, commit_message: str) -> str:
    """Commit a file to MM-Nexus-Website's `main` branch via GitHub's
    Contents API, creating or updating `path`. Returns the resulting
    commit SHA. No-ops (returns the existing SHA unchanged) if the content
    is byte-identical to what's already committed - the guard against
    double-click duplicate deploys. Shared by publish() (the post's
    Markdown) and publish_cover_image() (its generated cover PNG) - same
    commit mechanics, different path/content.

    Raises:
        MarketingBlogPublishError: if the GitHub PAT isn't configured, or
            the API call fails.
    """
    if not settings.marketing_cms_github_pat:
        raise MarketingBlogPublishError(
            "MARKETING_CMS_GITHUB_PAT is not configured - cannot publish."
        )

    encoded_content = base64.b64encode(content_bytes).decode("ascii")
    api_url = f"https://api.github.com/repos/{settings.marketing_cms_github_repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {settings.marketing_cms_github_pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        with httpx.Client(timeout=15) as client:
            existing_sha: str | None = None
            get_resp = client.get(
                api_url, headers=headers, params={"ref": settings.marketing_cms_github_branch}
            )
            if get_resp.status_code == 200:
                existing = get_resp.json()
                existing_sha = existing.get("sha")
                existing_content = (existing.get("content") or "").replace("\n", "")
                if existing_content == encoded_content:
                    # Content already matches what's live - no-op, no new commit.
                    return existing_sha or ""
            elif get_resp.status_code != 404:
                get_resp.raise_for_status()

            put_body = {
                "message": commit_message,
                "content": encoded_content,
                "branch": settings.marketing_cms_github_branch,
            }
            if existing_sha:
                put_body["sha"] = existing_sha

            put_resp = client.put(api_url, headers=headers, json=put_body)
            put_resp.raise_for_status()
            return put_resp.json()["commit"]["sha"]
    except httpx.HTTPError as exc:
        raise MarketingBlogPublishError(f"Failed to publish to GitHub: {exc}") from exc


def publish(post: MarketingBlogPost, markdown_body: str) -> str:
    """Commit the post's Markdown to MM-Nexus-Website's `main` branch,
    creating or updating src/content/blog/{slug}.md. Returns the resulting
    commit SHA - see _commit_file_to_github() for the no-op/error behavior.
    """
    file_content = _build_markdown_file(post, markdown_body)
    return _commit_file_to_github(
        f"src/content/blog/{post.slug}.md",
        file_content.encode("utf-8"),
        f"Publish blog post: {post.title}",
    )


_COVER_IMAGE_PROMPT_TEMPLATE = """A professional, abstract editorial illustration for a B2B technology \
and business consulting blog article titled "{title}" ({description}). Modern, clean, conceptual style - \
abstract geometric shapes, symbolic imagery, or subtle tech-adjacent visual metaphors representing the \
idea. Do not include any literal photos of people, screens, or interfaces. Do not include any text, \
words, letters, or numbers anywhere in the image. Wide, cinematic framing suitable as a blog hero \
banner, MM Nexus's brand tone: direct, professional, not corporate-stock-photo generic."""


def _cover_image_prompt(title: str, description: str) -> str:
    return _COVER_IMAGE_PROMPT_TEMPLATE.format(title=title, description=description)


def publish_cover_image(post: MarketingBlogPost, image_bytes: bytes) -> str:
    """Commit a generated cover image to MM-Nexus-Website's own repo at
    public/blog/covers/{slug}.png - deliberately not R2 (BFP's normal
    object storage): R2 access here is exclusively short-lived presigned
    URLs, the wrong shape for something embedded in a live page
    indefinitely. A committed static asset in the site's own repo has no
    expiry and needs no new infrastructure."""
    return _commit_file_to_github(
        f"public/blog/covers/{post.slug}.png",
        image_bytes,
        f"Add cover image: {post.title}",
    )


def generate_and_attach_cover_image(post: MarketingBlogPost) -> None:
    """Generate a cover image from the post's title/description and commit
    it, setting post.cover_image_url. Does not commit the DB session -
    callers own their own transaction boundary, matching this file's
    other orchestration functions.

    Raises:
        image_gen.ImageGenError: if OpenAI isn't configured or the call fails.
        MarketingBlogPublishError: if the GitHub commit fails.
    """
    prompt = _cover_image_prompt(post.title, post.description)
    image_bytes = image_gen.generate_cover_image(prompt)
    publish_cover_image(post, image_bytes)
    post.cover_image_url = f"/blog/covers/{post.slug}.png"


def publish_and_cross_post(post: MarketingBlogPost, markdown_body: str) -> tuple[str, str]:
    """Publish to the website, then best-effort share it on the LinkedIn
    company page. Returns (commit_sha, linkedin_status) where
    linkedin_status is one of "posted", "not configured", or
    "failed: <reason>" - never raises for a LinkedIn failure, since the
    website publish (already committed by this point) is the primary
    action and must not be undone by a secondary integration failing.
    """
    commit_sha = publish(post, markdown_body)

    article_url = f"{settings.marketing_site_public_url}/blog/{post.slug}"
    try:
        post_id = linkedin.post_company_update(f"{post.title}\n\n{post.description}", article_url)
        linkedin_status = "posted" if post_id else "not configured"
    except linkedin.LinkedInPostError as e:
        linkedin_status = f"failed: {e}"

    return commit_sha, linkedin_status
