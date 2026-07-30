"""API-level tests for the customer portal - authenticated management routes
plus the public, unauthenticated portal routes."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.customer import Customer
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import CurrentUser


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.customer_portal.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _make_org_owner(test_db: Session, plan_tier: str) -> CurrentUser:
    organization = Organization(id=uuid4(), name="Test Org", billing_email=f"{uuid4().hex[:8]}@example.com", plan_tier=plan_tier)
    test_db.add(organization)
    test_db.commit()

    business = Business(
        id=uuid4(), organization_id=organization.id, name="Test Business",
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


def _add_staff(test_db: Session, business_id) -> CurrentUser:
    user = User(
        id=uuid4(), business_id=business_id, email=f"{uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password123"), first_name="Staff", last_name="User",
        role="staff", is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return CurrentUser(
        user_id=str(user.id), business_id=str(business_id), email=user.email,
        role="staff", full_name="Staff User",
    )


def _auth_headers(user: CurrentUser) -> dict:
    token = create_access_token({
        "user_id": str(user.user_id), "business_id": str(user.business_id),
        "email": user.email, "role": user.role, "full_name": user.full_name,
    })
    return {"Authorization": f"Bearer {token}"}


def _make_customer(test_db: Session, business_id) -> Customer:
    customer = Customer(id=uuid4(), business_id=business_id, name="Acme Client")
    test_db.add(customer)
    test_db.commit()
    return customer


class TestPortalAccessManagementApi:
    def test_owner_on_growth_tier_can_generate(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        customer = _make_customer(test_db, owner.business_id)

        r = client.post(f"/api/v1/customers/{customer.id}/portal-access", headers=_auth_headers(owner))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["portal_url"].endswith(body["portal_url"].split("/")[-1])
        assert "/portal/" in body["portal_url"]

    def test_starter_tier_is_rejected(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "starter")
        customer = _make_customer(test_db, owner.business_id)

        r = client.post(f"/api/v1/customers/{customer.id}/portal-access", headers=_auth_headers(owner))
        assert r.status_code == 403

    def test_staff_role_is_rejected_on_growth_tier(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        staff = _add_staff(test_db, owner.business_id)
        customer = _make_customer(test_db, owner.business_id)

        r = client.post(f"/api/v1/customers/{customer.id}/portal-access", headers=_auth_headers(staff))
        assert r.status_code == 403

    def test_get_status_and_revoke(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        headers = _auth_headers(owner)
        customer = _make_customer(test_db, owner.business_id)

        r = client.get(f"/api/v1/customers/{customer.id}/portal-access", headers=headers)
        assert r.status_code == 200
        assert r.json() is None

        client.post(f"/api/v1/customers/{customer.id}/portal-access", headers=headers)

        r = client.get(f"/api/v1/customers/{customer.id}/portal-access", headers=headers)
        assert r.status_code == 200
        assert r.json() is not None

        r = client.delete(f"/api/v1/customers/{customer.id}/portal-access", headers=headers)
        assert r.status_code == 204

        r = client.get(f"/api/v1/customers/{customer.id}/portal-access", headers=headers)
        assert r.json() is None


class TestPublicPortalApi:
    def _generate_token(self, client: TestClient, owner: CurrentUser, customer_id) -> str:
        r = client.post(f"/api/v1/customers/{customer_id}/portal-access", headers=_auth_headers(owner))
        return r.json()["portal_url"].rsplit("/", 1)[-1]

    def test_garbage_token_returns_404(self, client: TestClient):
        r = client.get("/api/v1/portal/not-a-real-token")
        assert r.status_code == 404

    def test_valid_token_returns_customer_and_documents(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        customer = _make_customer(test_db, owner.business_id)
        customer_id = str(customer.id)
        client.post(
            "/api/v1/documents",
            data={"entity_type": "customer", "entity_id": customer_id},
            files={"file": ("worksheet.pdf", b"data", "application/pdf")},
            headers=_auth_headers(owner),
        )
        raw_token = self._generate_token(client, owner, customer_id)

        r = client.get(f"/api/v1/portal/{raw_token}")
        assert r.status_code == 200
        body = r.json()
        assert body["customer_name"] == "Acme Client"
        assert len(body["documents"]) == 1

    def test_revoked_token_returns_404(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        customer = _make_customer(test_db, owner.business_id)
        customer_id = str(customer.id)
        raw_token = self._generate_token(client, owner, customer_id)

        client.delete(f"/api/v1/customers/{customer_id}/portal-access", headers=_auth_headers(owner))

        r = client.get(f"/api/v1/portal/{raw_token}")
        assert r.status_code == 404

    def test_download_url_for_cross_customer_document_returns_404(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        headers = _auth_headers(owner)
        customer_a = _make_customer(test_db, owner.business_id)
        customer_b = _make_customer(test_db, owner.business_id)
        customer_a_id = str(customer_a.id)
        customer_b_id = str(customer_b.id)

        other_doc = client.post(
            "/api/v1/documents",
            data={"entity_type": "customer", "entity_id": customer_b_id},
            files={"file": ("other.pdf", b"data", "application/pdf")},
            headers=headers,
        ).json()

        raw_token = self._generate_token(client, owner, customer_a_id)

        r = client.get(f"/api/v1/portal/{raw_token}/documents/{other_doc['id']}/download-url")
        assert r.status_code == 404

    def test_download_url_for_own_document_succeeds(self, client: TestClient, test_db: Session):
        owner = _make_org_owner(test_db, "growth")
        headers = _auth_headers(owner)
        customer = _make_customer(test_db, owner.business_id)
        customer_id = str(customer.id)

        doc = client.post(
            "/api/v1/documents",
            data={"entity_type": "customer", "entity_id": customer_id},
            files={"file": ("mine.pdf", b"data", "application/pdf")},
            headers=headers,
        ).json()

        raw_token = self._generate_token(client, owner, customer_id)

        r = client.get(f"/api/v1/portal/{raw_token}/documents/{doc['id']}/download-url")
        assert r.status_code == 200
        assert r.json()["url"] == "https://signed.example/url"
