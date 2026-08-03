"""Payroll configuration API tests — deduction/benefit types, employee
assignments, timesheets (app/api/payroll.py)."""

import pytest
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


def make_employee(client: TestClient, token: str, **overrides) -> dict:
    payload = {"first_name": "Test", "last_name": "Employee", "gross_salary": "10000"}
    payload.update(overrides)
    r = client.post("/api/v1/hr/employees", json=payload, headers=auth(token))
    assert r.status_code == 201
    return r.json()


class TestDeductionTypes:
    def test_create_and_list(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/deduction-types",
            json={"name": "Medical Aid", "calculation": "fixed_amount", "default_amount": "500"},
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Medical Aid"
        assert data["is_active"] is True

        r = client.get("/api/v1/hr/deduction-types", headers=auth(token))
        assert r.status_code == 200
        assert any(d["name"] == "Medical Aid" for d in r.json())

    def test_update(self, client: TestClient, token: str):
        dt = client.post(
            "/api/v1/hr/deduction-types",
            json={"name": "Union Fee", "calculation": "fixed_amount", "default_amount": "50"},
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/deduction-types/{dt['id']}",
            json={"default_amount": "75"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert float(r.json()["default_amount"]) == 75.0


class TestBenefitTypes:
    def test_create_and_list(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/benefit-types",
            json={"name": "Gym Membership", "calculation": "fixed_amount", "default_amount": "300"},
            headers=auth(token),
        )
        assert r.status_code == 201
        r = client.get("/api/v1/hr/benefit-types", headers=auth(token))
        assert any(b["name"] == "Gym Membership" for b in r.json())


class TestEmployeeAssignments:
    def test_assign_and_remove_deduction(self, client: TestClient, token: str):
        emp = make_employee(client, token)
        dt = client.post(
            "/api/v1/hr/deduction-types",
            json={"name": "Loan Repayment", "calculation": "fixed_amount", "default_amount": "200"},
            headers=auth(token),
        ).json()

        r = client.post(
            "/api/v1/hr/employee-deductions",
            json={"employee_id": emp["id"], "deduction_type_id": dt["id"], "amount_override": "250"},
            headers=auth(token),
        )
        assert r.status_code == 201
        row = r.json()
        assert row["employee_name"] == "Test Employee"
        assert row["deduction_type_name"] == "Loan Repayment"
        assert float(row["amount_override"]) == 250.0

        r = client.get(f"/api/v1/hr/employee-deductions?employee_id={emp['id']}", headers=auth(token))
        assert len(r.json()) == 1

        r = client.delete(f"/api/v1/hr/employee-deductions/{row['id']}", headers=auth(token))
        assert r.status_code == 204
        r = client.get(f"/api/v1/hr/employee-deductions?employee_id={emp['id']}", headers=auth(token))
        assert len(r.json()) == 0

    def test_assign_and_remove_benefit(self, client: TestClient, token: str):
        emp = make_employee(client, token)
        bt = client.post(
            "/api/v1/hr/benefit-types",
            json={"name": "Cellphone Allowance", "calculation": "fixed_amount", "default_amount": "400"},
            headers=auth(token),
        ).json()

        r = client.post(
            "/api/v1/hr/employee-benefits",
            json={"employee_id": emp["id"], "benefit_type_id": bt["id"]},
            headers=auth(token),
        )
        assert r.status_code == 201
        row = r.json()

        r = client.get(f"/api/v1/hr/employee-benefits?employee_id={emp['id']}", headers=auth(token))
        assert len(r.json()) == 1

        r = client.delete(f"/api/v1/hr/employee-benefits/{row['id']}", headers=auth(token))
        assert r.status_code == 204


class TestTimesheets:
    def test_log_list_and_filter(self, client: TestClient, token: str):
        emp = make_employee(client, token, salary_type="hourly", gross_salary="150")

        r = client.post(
            "/api/v1/hr/timesheets",
            json={"employee_id": emp["id"], "work_date": "2025-06-02", "hours_worked": "8", "notes": "Normal day"},
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["employee_name"] == "Test Employee"
        assert float(data["hours_worked"]) == 8.0

        r = client.get(f"/api/v1/hr/timesheets?employee_id={emp['id']}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = client.get(
            f"/api/v1/hr/timesheets?employee_id={emp['id']}&date_from=2025-07-01",
            headers=auth(token),
        )
        assert r.json()["total"] == 0

    def test_delete_timesheet(self, client: TestClient, token: str):
        emp = make_employee(client, token, salary_type="hourly", gross_salary="150")
        ts = client.post(
            "/api/v1/hr/timesheets",
            json={"employee_id": emp["id"], "work_date": "2025-06-03", "hours_worked": "8"},
            headers=auth(token),
        ).json()
        r = client.delete(f"/api/v1/hr/timesheets/{ts['id']}", headers=auth(token))
        assert r.status_code == 204
