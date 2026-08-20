#!/usr/bin/env python
"""One-off: generate and attach an AI cover image to every existing marketing
blog post that doesn't have one yet.

Idempotent - only touches rows where cover_image_url is still NULL, so it's
safe to re-run (e.g. if a prior run partially failed on one post). Each
image is a real OpenAI API call with real cost - run deliberately, not on
a schedule.

Usage:
    python scripts/backfill_blog_cover_images.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.integrations.image_gen import ImageGenError  # noqa: E402
from app.models.marketing_blog_post import MarketingBlogPost  # noqa: E402
from app.services import marketing_blog  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        posts = db.query(MarketingBlogPost).filter(MarketingBlogPost.cover_image_url.is_(None)).all()
        if not posts:
            print("No posts are missing a cover image.")
            return

        print(f"Found {len(posts)} post(s) without a cover image.")
        succeeded, failed = 0, 0
        for post in posts:
            if not post.title or not post.description:
                print(f"  SKIP  {post.slug!r} - missing title/description.")
                continue
            try:
                marketing_blog.generate_and_attach_cover_image(post)
                db.commit()
                succeeded += 1
                print(f"  OK    {post.slug!r} -> {post.cover_image_url}")
            except (ImageGenError, marketing_blog.MarketingBlogPublishError) as e:
                db.rollback()
                failed += 1
                print(f"  FAIL  {post.slug!r} - {e}", file=sys.stderr)

        print(f"Done. {succeeded} succeeded, {failed} failed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
