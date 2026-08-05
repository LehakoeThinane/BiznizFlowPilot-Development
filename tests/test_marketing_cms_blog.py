"""API + service tests for the marketing CMS blog CRUD, AI-generate, and
GitHub-backed publish flow."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.models.marketing_cms_admin import MarketingCmsAdmin


def auth(client, admin: MarketingCmsAdmin) -> dict:
    r = client.post(
        "/api/v1/marketing/cms/auth/login",
        json={"email": admin.email, "password": "password123"},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestListAndCreatePosts:
    def test_list_starts_empty(self, client, marketing_cms_admin):
        r = client.get("/api/v1/marketing/cms/blog", headers=auth(client, marketing_cms_admin))
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_create_draft(self, client, marketing_cms_admin):
        r = client.post(
            "/api/v1/marketing/cms/blog",
            json={"title": "My New Post", "slug": "my-new-post"},
            headers=auth(client, marketing_cms_admin),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["slug"] == "my-new-post"
        assert body["status"] == "draft"
        assert body["content_blocks"] == []

    def test_duplicate_slug_rejected(self, client, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        client.post("/api/v1/marketing/cms/blog", json={"title": "A", "slug": "dupe"}, headers=headers)
        r = client.post("/api/v1/marketing/cms/blog", json={"title": "B", "slug": "dupe"}, headers=headers)
        assert r.status_code == 400

    def test_requires_auth(self, client):
        r = client.post("/api/v1/marketing/cms/blog", json={"title": "A", "slug": "a"})
        assert r.status_code == 401

    def test_list_filters_by_status(self, client, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        client.post("/api/v1/marketing/cms/blog", json={"title": "A", "slug": "post-a"}, headers=headers)
        r = client.get("/api/v1/marketing/cms/blog?status=published", headers=headers)
        assert r.status_code == 200
        assert r.json()["items"] == []
        r = client.get("/api/v1/marketing/cms/blog?status=draft", headers=headers)
        assert len(r.json()["items"]) == 1


class TestGetAndUpdatePost:
    def test_404_for_missing(self, client, marketing_cms_admin):
        r = client.get(f"/api/v1/marketing/cms/blog/{uuid4()}", headers=auth(client, marketing_cms_admin))
        assert r.status_code == 404

    def test_autosave_updates_fields(self, client, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "Draft", "slug": "draft-post"}, headers=headers
        ).json()

        blocks = [{"type": "paragraph", "content": "Hello world"}]
        r = client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "A description", "content_blocks": blocks},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["description"] == "A description"
        assert body["content_blocks"] == blocks
        assert body["title"] == "Draft"  # untouched field preserved


class TestDeletePost:
    def test_delete_draft(self, client, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "Temp", "slug": "temp-post"}, headers=headers
        ).json()
        r = client.delete(f"/api/v1/marketing/cms/blog/{created['id']}", headers=headers)
        assert r.status_code == 204
        assert client.get(f"/api/v1/marketing/cms/blog/{created['id']}", headers=headers).status_code == 404

    def test_cannot_delete_published_post(self, client, test_db, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "Live", "slug": "live-post"}, headers=headers
        ).json()
        from app.repositories.marketing_blog_post import MarketingBlogPostRepository

        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(created["id"]))
        post.status = "published"
        test_db.commit()

        r = client.delete(f"/api/v1/marketing/cms/blog/{created['id']}", headers=headers)
        assert r.status_code == 400


class TestGeneratePost:
    def test_generate_returns_markdown_from_engine(self, client, marketing_cms_admin, monkeypatch):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "Draft", "slug": "gen-post"}, headers=headers
        ).json()

        fake_response = type("R", (), {"reply": "## Generated heading\n\nGenerated body text."})()
        monkeypatch.setattr(
            "app.services.marketing_blog.get_engine",
            lambda: type("E", (), {"chat": staticmethod(lambda messages, system_prompt: fake_response)})(),
        )

        r = client.post(
            f"/api/v1/marketing/cms/blog/{created['id']}/generate",
            json={"topic": "Why custom websites beat template builders"},
            headers=headers,
        )
        assert r.status_code == 200
        assert "Generated heading" in r.json()["markdown"]

    def test_generate_404_for_missing_post(self, client, marketing_cms_admin):
        r = client.post(
            f"/api/v1/marketing/cms/blog/{uuid4()}/generate",
            json={"topic": "Anything"},
            headers=auth(client, marketing_cms_admin),
        )
        assert r.status_code == 404


def _fake_github_client(*, existing_content_b64: str | None, existing_sha: str = "old-sha", new_commit_sha: str = "new-sha"):
    """Build a MagicMock standing in for httpx.Client(...) as a context manager."""
    mock_client = MagicMock()

    get_response = MagicMock()
    if existing_content_b64 is None:
        get_response.status_code = 404
    else:
        get_response.status_code = 200
        get_response.json.return_value = {"sha": existing_sha, "content": existing_content_b64}
    mock_client.get.return_value = get_response

    put_response = MagicMock()
    put_response.raise_for_status.return_value = None
    put_response.json.return_value = {"commit": {"sha": new_commit_sha}}
    mock_client.put.return_value = put_response

    context_manager = MagicMock()
    context_manager.__enter__.return_value = mock_client
    context_manager.__exit__.return_value = False
    return context_manager, mock_client


class TestPublishPost:
    def test_publish_new_post_creates_file(self, client, test_db, marketing_cms_admin, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog",
            json={"title": "Publishable Post", "slug": "publishable-post"},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "A real description."},
            headers=headers,
        )

        context_manager, mock_client = _fake_github_client(existing_content_b64=None)
        with patch("app.services.marketing_blog.httpx.Client", return_value=context_manager):
            r = client.post(
                f"/api/v1/marketing/cms/blog/{created['id']}/publish",
                json={"markdown_body": "Some published body text."},
                headers=headers,
            )
        assert r.status_code == 200
        body = r.json()
        assert body["published"] is True
        assert body["github_commit_sha"] == "new-sha"
        mock_client.put.assert_called_once()

        detail = client.get(f"/api/v1/marketing/cms/blog/{created['id']}", headers=headers).json()
        assert detail["status"] == "published"
        assert detail["github_commit_sha"] == "new-sha"

    def test_publish_requires_title_and_description(self, client, marketing_cms_admin, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "No Description", "slug": "no-desc"}, headers=headers
        ).json()
        r = client.post(
            f"/api/v1/marketing/cms/blog/{created['id']}/publish",
            json={"markdown_body": "Body."},
            headers=headers,
        )
        assert r.status_code == 400

    def test_publish_idempotent_when_content_unchanged(self, client, test_db, marketing_cms_admin, monkeypatch):
        """Publishing twice with unchanged content produces exactly one
        commit - the guard against double-click duplicate deploys."""
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog",
            json={"title": "Idempotent Post", "slug": "idempotent-post"},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "Fixed description."},
            headers=headers,
        )
        markdown_body = "Body that will not change."

        # First publish: file doesn't exist yet.
        ctx1, mock_client1 = _fake_github_client(existing_content_b64=None, new_commit_sha="first-sha")
        with patch("app.services.marketing_blog.httpx.Client", return_value=ctx1):
            first = client.post(
                f"/api/v1/marketing/cms/blog/{created['id']}/publish",
                json={"markdown_body": markdown_body},
                headers=headers,
            )
        assert first.json()["github_commit_sha"] == "first-sha"

        # Recompute the exact same encoded content the service would build,
        # to simulate GitHub now returning that file with matching content.
        # Reuse the test_db fixture session (the same in-memory test DB the
        # API itself used), not a real SessionLocal() connection.
        from app.repositories.marketing_blog_post import MarketingBlogPostRepository
        from app.services import marketing_blog

        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(created["id"]))
        file_content = marketing_blog._build_markdown_file(post, markdown_body)
        encoded = base64.b64encode(file_content.encode("utf-8")).decode("ascii")

        ctx2, mock_client2 = _fake_github_client(existing_content_b64=encoded, existing_sha="first-sha")
        with patch("app.services.marketing_blog.httpx.Client", return_value=ctx2):
            second = client.post(
                f"/api/v1/marketing/cms/blog/{created['id']}/publish",
                json={"markdown_body": markdown_body},
                headers=headers,
            )
        assert second.status_code == 200
        assert second.json()["github_commit_sha"] == "first-sha"
        mock_client2.put.assert_not_called()

    def test_build_markdown_file_includes_cover_image_when_set(self, client, test_db, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog",
            json={"title": "Cover Image Post", "slug": "cover-image-post"},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "Has a cover.", "cover_image_url": "/blog/covers/cover-image-post.png"},
            headers=headers,
        )

        from app.repositories.marketing_blog_post import MarketingBlogPostRepository
        from app.services import marketing_blog

        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(created["id"]))
        file_content = marketing_blog._build_markdown_file(post, "Body.")
        assert 'coverImage: "/blog/covers/cover-image-post.png"' in file_content

    def test_build_markdown_file_omits_cover_image_when_unset(self, client, test_db, marketing_cms_admin):
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog",
            json={"title": "No Cover Post", "slug": "no-cover-post"},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "No cover."},
            headers=headers,
        )

        from app.repositories.marketing_blog_post import MarketingBlogPostRepository
        from app.services import marketing_blog

        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(created["id"]))
        file_content = marketing_blog._build_markdown_file(post, "Body.")
        assert "coverImage:" not in file_content

    def test_publish_without_pat_configured_fails_cleanly(self, client, marketing_cms_admin, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "")
        headers = auth(client, marketing_cms_admin)
        created = client.post(
            "/api/v1/marketing/cms/blog", json={"title": "No PAT", "slug": "no-pat"}, headers=headers
        ).json()
        client.patch(
            f"/api/v1/marketing/cms/blog/{created['id']}",
            json={"description": "Desc."},
            headers=headers,
        )
        r = client.post(
            f"/api/v1/marketing/cms/blog/{created['id']}/publish",
            json={"markdown_body": "Body."},
            headers=headers,
        )
        assert r.status_code == 502
