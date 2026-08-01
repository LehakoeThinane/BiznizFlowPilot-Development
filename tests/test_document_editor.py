"""Tests for the in-app document editor: compose/draft-autosave/finish, and
the Growth+ tier gate on all three routes."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.integrations.object_storage import ObjectStorageError
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import CurrentUser


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


_STORAGE = {}


def _fake_upload_at_key(key, content, content_type):
    _STORAGE[key] = content


def _fake_get(key):
    if key not in _STORAGE:
        raise ObjectStorageError(f"No such key: {key}")
    return _STORAGE[key]


def _fake_delete(key):
    _STORAGE.pop(key, None)


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    _STORAGE.clear()
    with patch("app.services.document.object_storage.upload", return_value="fake/key.txt"), \
         patch("app.services.document_checkout.object_storage.upload", return_value="fake/key2.txt"), \
         patch("app.services.document_editor.object_storage.upload_at_key", side_effect=_fake_upload_at_key), \
         patch("app.services.document_editor.object_storage.get", side_effect=_fake_get), \
         patch("app.services.document_editor.object_storage.delete", side_effect=_fake_delete):
        yield


class TestSanitize:
    """_sanitize() (app/services/document_editor.py) had zero direct test
    coverage before this - every existing test in this file exercises it
    only indirectly through save_draft()/finish(), which never sends
    anything adversarial. Testing it directly here is the only thing that
    would actually catch a regression in the allowlist (e.g. a future
    toolbar addition whose rendered HTML silently gets stripped, or an
    accidentally-too-permissive CSS/tag allowance)."""

    def test_preserves_all_toolbar_formatting(self):
        from app.services.document_editor import _sanitize

        html = (
            '<p style="text-align: center; margin-left: 3em">'
            '<span style="color: rgb(220, 38, 38)">colored</span> '
            '<mark data-color="#fef08a" style="background-color: #fef08a; color: inherit">highlighted</mark> '
            '<u>underlined</u> <strong>bold</strong> <em>italic</em>'
            '</p>'
            '<h2>Heading</h2>'
            '<ul><li><p>item</p></li></ul>'
            '<ol><li><p>item</p></li></ol>'
            '<blockquote><p>quoted</p></blockquote>'
            '<p><a href="https://example.com" target="_blank" rel="noopener noreferrer">a link</a></p>'
        )
        result = _sanitize(html)
        assert 'text-align: center' in result
        assert 'margin-left: 3em' in result
        assert 'color: rgb(220, 38, 38)' in result
        assert '<mark data-color="#fef08a"' in result
        assert 'background-color: #fef08a' in result
        assert '<u>underlined</u>' in result
        assert '<h2>Heading</h2>' in result
        assert '<blockquote><p>quoted</p></blockquote>' in result
        assert 'href="https://example.com"' in result
        assert 'target="_blank"' in result

    def test_strips_script_tags(self):
        from app.services.document_editor import _sanitize

        result = _sanitize('<p>hello</p><script>alert(document.cookie)</script>')
        assert '<script>' not in result
        assert '</script>' not in result

    def test_strips_event_handler_attributes(self):
        from app.services.document_editor import _sanitize

        result = _sanitize('<p onclick="alert(1)">hello</p>')
        assert 'onclick' not in result

    def test_strips_disallowed_tags_like_img_and_iframe(self):
        from app.services.document_editor import _sanitize

        result = _sanitize('<p>text</p><img src="x" onerror="alert(1)"><iframe src="evil.com"></iframe>')
        assert '<img' not in result
        assert '<iframe' not in result
        assert 'onerror' not in result

    def test_strips_javascript_protocol_from_links(self):
        from app.services.document_editor import _sanitize

        result = _sanitize('<a href="javascript:alert(1)">bad link</a>')
        assert 'javascript:' not in result

    def test_strips_disallowed_css_properties_but_keeps_allowed_ones(self):
        from app.services.document_editor import _sanitize

        result = _sanitize(
            '<p style="text-align: center; position: fixed; top: 0; display: block; z-index: 9999">text</p>'
        )
        assert 'text-align: center' in result
        assert 'position' not in result
        assert 'z-index' not in result
        assert 'display' not in result

    def test_strips_style_from_disallowed_tag_like_div(self):
        from app.services.document_editor import _sanitize

        result = _sanitize('<div style="color: red">not an allowed tag</div>')
        assert '<div' not in result


def _make_org_owner(test_db: Session, plan_tier: str) -> CurrentUser:
    """Same pattern as tests/test_onboarding.py - a fresh org at a specific
    plan tier, with an owner user, for the tier-gating (403) tests. The
    shared `registered_user` fixture defaults to "legacy", which already has
    full access to every gated feature - fine for the "allowed" tests, but
    useless for proving starter-tier actually gets rejected."""
    organization = Organization(id=uuid4(), name="Starter Org", billing_email=f"{uuid4().hex[:8]}@example.com", plan_tier=plan_tier)
    test_db.add(organization)
    test_db.commit()

    business = Business(
        id=uuid4(), organization_id=organization.id, name="Starter Business",
        email=f"{uuid4().hex[:8]}@example.com", phone="+1234567890", is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()

    user = User(
        id=uuid4(), business_id=business.id, email=f"{uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password123"), first_name="Owner", last_name="User",
        role="owner", is_active=True,
    )
    test_db.add(user)
    test_db.commit()

    return CurrentUser(
        user_id=str(user.id), business_id=str(business.id), organization_id=str(organization.id),
        email=user.email, role="owner", full_name="Owner User",
    )


def _add_colleague(test_db: Session, business_id, organization_id) -> CurrentUser:
    """A second user in the same business, for permission tests where the
    tier-gate must pass but a specific user's lack of checkout ownership
    should still be what's actually being tested."""
    user = User(
        id=uuid4(), business_id=business_id, email=f"{uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password123"), first_name="Colleague", last_name="User",
        role="staff", is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return CurrentUser(
        user_id=str(user.id), business_id=str(business_id), organization_id=str(organization_id),
        email=user.email, role="staff", full_name="Colleague User",
    )


def _auth_headers(user: CurrentUser) -> dict:
    tok = create_access_token({
        "user_id": str(user.user_id), "business_id": str(user.business_id),
        "email": user.email, "role": user.role, "full_name": user.full_name,
    })
    return {"Authorization": f"Bearer {tok}"}


class TestComposeDraftFinish:
    def test_compose_creates_a_checked_out_empty_document(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Meeting Notes"},
            headers=auth(token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["filename"] == "Meeting Notes.html"
        assert body["version"] == 1
        assert body["checked_out_by"] is not None

    def test_draft_autosave_does_not_bump_version_or_create_a_version_row(self, client: TestClient, token: str):
        doc_id = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Draft Doc"},
            headers=auth(token),
        ).json()["id"]

        for i in range(3):
            r = client.patch(
                f"/api/v1/documents/{doc_id}/draft",
                json={"content_html": f"<p>revision {i}</p>"},
                headers=auth(token),
            )
            assert r.status_code == 204

        versions = client.get(f"/api/v1/documents/{doc_id}/versions", headers=auth(token))
        assert versions.json()["items"] == []

    def test_finish_creates_exactly_one_new_version_and_clears_checkout(self, client: TestClient, token: str):
        doc_id = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Report"},
            headers=auth(token),
        ).json()["id"]
        client.patch(f"/api/v1/documents/{doc_id}/draft", json={"content_html": "<p>final content</p>"}, headers=auth(token))

        r = client.post(f"/api/v1/documents/{doc_id}/finish", headers=auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 2
        assert body["checked_out_by"] is None

        versions = client.get(f"/api/v1/documents/{doc_id}/versions", headers=auth(token)).json()["items"]
        assert len(versions) == 1

    def test_finish_without_any_autosave_just_releases_the_checkout(self, client: TestClient, token: str):
        doc_id = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Untouched"},
            headers=auth(token),
        ).json()["id"]

        r = client.post(f"/api/v1/documents/{doc_id}/finish", headers=auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 1
        assert body["checked_out_by"] is None

    def test_draft_save_by_non_checkout_holder_is_rejected(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        colleague = _add_colleague(test_db, owner.business_id, owner.organization_id)

        doc_id = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Locked"},
            headers=_auth_headers(owner),
        ).json()["id"]

        r = client.patch(
            f"/api/v1/documents/{doc_id}/draft",
            json={"content_html": "<p>sneaky edit</p>"},
            headers=_auth_headers(colleague),
        )
        assert r.status_code == 403


class TestDocumentAuthoringTierGate:
    def test_starter_tier_cannot_compose(self, client: TestClient, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        r = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Nope"},
            headers=_auth_headers(user),
        )
        assert r.status_code == 403

    def test_growth_tier_can_compose(self, client: TestClient, test_db: Session):
        user = _make_org_owner(test_db, "growth")
        r = client.post(
            "/api/v1/documents/compose",
            json={"entity_type": "lead", "entity_id": str(uuid4()), "title": "Yes"},
            headers=_auth_headers(user),
        )
        assert r.status_code == 201

    def test_starter_tier_cannot_save_draft_or_finish(self, client: TestClient, test_db: Session):
        # require_feature runs before the route body, so a starter-tier
        # caller gets 403 on /draft and /finish even for a made-up id -
        # the gate is on the caller's own org tier, not document ownership.
        starter_user = _make_org_owner(test_db, "starter")
        fake_doc_id = str(uuid4())

        draft_attempt = client.patch(
            f"/api/v1/documents/{fake_doc_id}/draft",
            json={"content_html": "<p>x</p>"},
            headers=_auth_headers(starter_user),
        )
        assert draft_attempt.status_code == 403

        finish_attempt = client.post(f"/api/v1/documents/{fake_doc_id}/finish", headers=_auth_headers(starter_user))
        assert finish_attempt.status_code == 403
