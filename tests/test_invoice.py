"""Invoice API tests — CRUD, line items, status lifecycle, PDF."""

import pytest
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


SAMPLE_LINE = {
    "description": "Widget Pro",
    "quantity": "2",
    "unit_price": "500.00",
    "discount_percent": "10",
    "tax_rate": "15",
}


def make_invoice(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "issue_date": "2026-05-01",
        "line_items": [SAMPLE_LINE],
    }
    payload.update(overrides)
    r = client.post("/api/v1/invoices", json=payload, headers=auth(token))
    assert r.status_code == 201
    return r.json()


class TestInvoiceCreate:
    def test_create_invoice_basic(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        assert inv["status"] == "draft"
        assert inv["invoice_number"].startswith("INV-")
        assert len(inv["line_items"]) == 1

    def test_invoice_totals_calculated(self, client: TestClient, token: str):
        """qty=2, price=500, disc=10%, tax=15%
        subtotal_line = 2*500 = 1000
        after_disc    = 1000 * 0.9 = 900
        tax           = 900 * 0.15 = 135
        line total    = 900 + 135 = 1035
        """
        inv = make_invoice(client, token)
        assert float(inv["subtotal"]) == 1000.0
        assert float(inv["discount_amount"]) == 100.0
        assert float(inv["tax_amount"]) == 135.0
        assert float(inv["total_amount"]) == 1035.0

    def test_create_invoice_no_line_items(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/invoices",
            json={"issue_date": "2026-05-01", "line_items": []},
            headers=auth(token),
        )
        assert r.status_code == 201
        assert float(r.json()["total_amount"]) == 0.0

    def test_invoice_numbers_sequential(self, client: TestClient, token: str):
        inv1 = make_invoice(client, token)
        inv2 = make_invoice(client, token)
        n1 = int(inv1["invoice_number"].split("-")[1])
        n2 = int(inv2["invoice_number"].split("-")[1])
        assert n2 == n1 + 1

    def test_create_invoice_requires_issue_date(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/invoices",
            json={"line_items": []},
            headers=auth(token),
        )
        assert r.status_code == 422


class TestInvoiceList:
    def test_list_invoices_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/invoices", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_invoices(self, client: TestClient, token: str):
        make_invoice(client, token)
        make_invoice(client, token)
        r = client.get("/api/v1/invoices", headers=auth(token))
        assert r.json()["total"] == 2

    def test_filter_by_status(self, client: TestClient, token: str):
        make_invoice(client, token)
        inv2 = make_invoice(client, token)
        client.patch(
            f"/api/v1/invoices/{inv2['id']}/status",
            json={"status": "sent"},
            headers=auth(token),
        )
        r = client.get("/api/v1/invoices?status=sent", headers=auth(token))
        assert r.json()["total"] == 1

    def test_get_invoice_by_id(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        r = client.get(f"/api/v1/invoices/{inv['id']}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == inv["id"]

    def test_get_nonexistent_invoice(self, client: TestClient, token: str):
        from uuid import uuid4
        r = client.get(f"/api/v1/invoices/{uuid4()}", headers=auth(token))
        assert r.status_code == 404


class TestInvoiceStatus:
    def test_mark_sent(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        r = client.patch(
            f"/api/v1/invoices/{inv['id']}/status",
            json={"status": "sent"},
            headers=auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "sent"
        assert data["sent_at"] is not None

    def test_mark_paid(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        r = client.patch(
            f"/api/v1/invoices/{inv['id']}/status",
            json={"status": "paid"},
            headers=auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "paid"
        assert data["paid_at"] is not None


class TestInvoicePdf:
    def test_pdf_returns_html(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        r = client.get(f"/api/v1/invoices/{inv['id']}/pdf", headers=auth(token))
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert inv["invoice_number"] in r.text
        assert "INVOICE" in r.text

    def test_pdf_not_found(self, client: TestClient, token: str):
        from uuid import uuid4
        r = client.get(f"/api/v1/invoices/{uuid4()}/pdf", headers=auth(token))
        assert r.status_code == 404


class TestInvoiceDelete:
    def test_delete_draft_invoice(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        r = client.delete(f"/api/v1/invoices/{inv['id']}", headers=auth(token))
        assert r.status_code == 204

    def test_cannot_delete_sent_invoice(self, client: TestClient, token: str):
        inv = make_invoice(client, token)
        client.patch(
            f"/api/v1/invoices/{inv['id']}/status",
            json={"status": "sent"},
            headers=auth(token),
        )
        r = client.delete(f"/api/v1/invoices/{inv['id']}", headers=auth(token))
        assert r.status_code == 400
