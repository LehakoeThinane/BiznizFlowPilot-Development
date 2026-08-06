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


def publish(post: MarketingBlogPost, markdown_body: str) -> str:
    """Commit the post's Markdown to MM-Nexus-Website's `main` branch,
    creating or updating src/content/blog/{slug}.md. Returns the resulting
    commit SHA. No-ops (returns the existing SHA unchanged) if the computed
    file content is byte-identical to what's already committed - the guard
    against double-click duplicate deploys.

    Raises:
        MarketingBlogPublishError: if the GitHub PAT isn't configured, or
            the API call fails.
    """
    if not settings.marketing_cms_github_pat:
        raise MarketingBlogPublishError(
            "MARKETING_CMS_GITHUB_PAT is not configured - cannot publish."
        )

    file_content = _build_markdown_file(post, markdown_body)
    encoded_content = base64.b64encode(file_content.encode("utf-8")).decode("ascii")
    path = f"src/content/blog/{post.slug}.md"
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
                "message": f"Publish blog post: {post.title}",
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
