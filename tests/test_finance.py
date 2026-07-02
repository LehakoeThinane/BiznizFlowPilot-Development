"""Finance API tests — expense categories, expenses, P&L summary."""

from datetime import date

import pytest
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


# ── Categories ──────────────────────────────────────────────────────────────

class TestExpenseCategories:
    def test_list_categories_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/finance/categories", headers=auth(token))
        assert r.status_code == 200
        assert r.json() == []

    def test_create_category(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/finance/categories",
            json={"name": "Travel", "description": "Business travel costs"},
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Travel"
        assert data["description"] == "Business travel costs"
        assert data["is_active"] is True

    def test_create_category_requires_name(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/finance/categories",
            json={"description": "No name"},
            headers=auth(token),
        )
        assert r.status_code == 422

    def test_list_categories_after_create(self, client: TestClient, token: str):
        client.post("/api/v1/finance/categories", json={"name": "Marketing"}, headers=auth(token))
        r = client.get("/api/v1/finance/categories", headers=auth(token))
        assert r.status_code == 200
        names = [c["name"] for c in r.json()]
        assert "Marketing" in names

    def test_update_category(self, client: TestClient, token: str):
        create = client.post(
            "/api/v1/finance/categories", json={"name": "Ops"}, headers=auth(token)
        )
        cat_id = create.json()["id"]
        r = client.patch(
            f"/api/v1/finance/categories/{cat_id}",
            json={"name": "Operations"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Operations"

    def test_update_nonexistent_category(self, client: TestClient, token: str):
        from uuid import uuid4
        r = client.patch(
            f"/api/v1/finance/categories/{uuid4()}",
            json={"name": "Ghost"},
            headers=auth(token),
        )
        assert r.status_code == 404


# ── Expenses ────────────────────────────────────────────────────────────────

class TestExpenses:
    def test_list_expenses_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/finance/expenses", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []

    def test_create_expense(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/finance/expenses",
            json={
                "date": "2026-05-01",
                "amount": "1500.00",
                "description": "Office supplies",
                "vendor": "Builders Warehouse",
            },
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["description"] == "Office supplies"
        assert float(data["amount"]) == 1500.0

    def test_create_expense_with_category(self, client: TestClient, token: str):
        cat = client.post(
            "/api/v1/finance/categories", json={"name": "Rent"}, headers=auth(token)
        ).json()
        r = client.post(
            "/api/v1/finance/expenses",
            json={
                "date": "2026-05-01",
                "amount": "12000.00",
                "description": "Monthly rent",
                "category_id": cat["id"],
            },
            headers=auth(token),
        )
        assert r.status_code == 201
        assert r.json()["category_id"] == cat["id"]
        assert r.json()["category_name"] == "Rent"

    def test_list_expenses_pagination(self, client: TestClient, token: str):
        for i in range(3):
            client.post(
                "/api/v1/finance/expenses",
                json={"date": "2026-05-01", "amount": "100", "description": f"Expense {i}"},
                headers=auth(token),
            )
        r = client.get("/api/v1/finance/expenses?limit=2&skip=0", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_update_expense(self, client: TestClient, token: str):
        exp = client.post(
            "/api/v1/finance/expenses",
            json={"date": "2026-05-01", "amount": "500", "description": "Misc"},
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/finance/expenses/{exp['id']}",
            json={"amount": "750.00"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert float(r.json()["amount"]) == 750.0

    def test_delete_expense(self, client: TestClient, token: str):
        exp = client.post(
            "/api/v1/finance/expenses",
            json={"date": "2026-05-01", "amount": "200", "description": "Delete me"},
            headers=auth(token),
        ).json()
        r = client.delete(f"/api/v1/finance/expenses/{exp['id']}", headers=auth(token))
        assert r.status_code == 204
        r2 = client.get("/api/v1/finance/expenses", headers=auth(token))
        assert not any(e["id"] == exp["id"] for e in r2.json()["items"])


# ── Summary ─────────────────────────────────────────────────────────────────

class TestFinanceSummary:
    def test_summary_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/finance/summary?period=this_month", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert float(data["revenue"]) == 0.0
        assert float(data["expenses"]) == 0.0
        assert float(data["net_profit"]) == 0.0

    def test_summary_reflects_expenses(self, client: TestClient, token: str):
        today = date.today().isoformat()
        client.post(
            "/api/v1/finance/expenses",
            json={"date": today, "amount": "3000", "description": "Test"},
            headers=auth(token),
        )
        r = client.get("/api/v1/finance/summary?period=this_month", headers=auth(token))
        assert r.status_code == 200
        assert float(r.json()["expenses"]) == 3000.0

    def test_summary_all_periods(self, client: TestClient, token: str):
        for period in ["this_month", "last_month", "ytd", "this_year"]:
            r = client.get(f"/api/v1/finance/summary?period={period}", headers=auth(token))
            assert r.status_code == 200
            assert "period_label" in r.json()

    def test_summary_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/finance/summary")
        assert r.status_code == 401
