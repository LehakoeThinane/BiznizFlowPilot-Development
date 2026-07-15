"""HR & Payroll API tests — departments, employees, leave, payroll."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.schemas.auth import CurrentUser


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _auth_headers(user: CurrentUser) -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": str(user.user_id),
            "business_id": str(user.business_id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


# ── Departments ──────────────────────────────────────────────────────────────

class TestDepartments:
    def test_list_departments_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/hr/departments", headers=auth(token))
        assert r.status_code == 200
        assert r.json() == []

    def test_create_department(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/departments",
            json={"name": "Engineering", "description": "Tech team"},
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Engineering"
        assert data["employee_count"] == 0

    def test_update_department(self, client: TestClient, token: str):
        dept = client.post(
            "/api/v1/hr/departments", json={"name": "HR"}, headers=auth(token)
        ).json()
        r = client.patch(
            f"/api/v1/hr/departments/{dept['id']}",
            json={"description": "Human Resources"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["description"] == "Human Resources"


# ── Employees ────────────────────────────────────────────────────────────────

class TestEmployees:
    def test_list_employees_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/hr/employees", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_create_employee(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/employees",
            json={
                "first_name": "Thabo",
                "last_name": "Mokoena",
                "position": "Developer",
                "employment_type": "full_time",
                "salary_type": "monthly",
                "gross_salary": "25000.00",
                "email": "thabo@test.com",
            },
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["first_name"] == "Thabo"
        assert data["full_name"] == "Thabo Mokoena"
        assert float(data["gross_salary"]) == 25000.0
        assert data["is_active"] is True

    def test_create_employee_requires_name(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/employees",
            json={"employment_type": "full_time", "gross_salary": "10000"},
            headers=auth(token),
        )
        assert r.status_code == 422

    def test_get_employee(self, client: TestClient, token: str):
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Jane", "last_name": "Smith", "gross_salary": "15000"},
            headers=auth(token),
        ).json()
        r = client.get(f"/api/v1/hr/employees/{emp['id']}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == emp["id"]

    def test_update_employee(self, client: TestClient, token: str):
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "John", "last_name": "Doe", "gross_salary": "20000"},
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/employees/{emp['id']}",
            json={"position": "Senior Developer", "gross_salary": "30000"},
            headers=auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["position"] == "Senior Developer"
        assert float(data["gross_salary"]) == 30000.0

    def test_list_employees_filter_by_department(self, client: TestClient, token: str):
        dept = client.post(
            "/api/v1/hr/departments", json={"name": "Sales"}, headers=auth(token)
        ).json()
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Alice", "last_name": "A", "gross_salary": "18000", "department_id": dept["id"]},
            headers=auth(token),
        )
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Bob", "last_name": "B", "gross_salary": "18000"},
            headers=auth(token),
        )
        r = client.get(f"/api/v1/hr/employees?department_id={dept['id']}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["first_name"] == "Alice"


class TestEmployeeEmailDomain:
    def test_unrestricted_org_accepts_any_email(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "No", "last_name": "Restriction", "email": "person@gmail.com"},
            headers=auth(token),
        )
        assert r.status_code == 201

    def test_rejects_email_outside_authorized_domain(self, client: TestClient, owner_user, org_admin_user):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "mmnexus.co.za", "is_primary": True},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Personal", "last_name": "Email", "email": "someone@gmail.com"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400
        assert "not authorized" in r.json()["detail"]

    def test_accepts_email_matching_authorized_domain(self, client: TestClient, owner_user, org_admin_user):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "mmnexus.co.za", "is_primary": True},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Work", "last_name": "Email", "email": "sifiso@mmnexus.co.za"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201

    def test_no_email_is_always_allowed(self, client: TestClient, owner_user, org_admin_user):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "mmnexus.co.za", "is_primary": True},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "No", "last_name": "Email"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201

    def test_update_also_validates_domain(self, client: TestClient, owner_user, org_admin_user):
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Update", "last_name": "Me"},
            headers=_auth_headers(owner_user),
        ).json()
        client.post(
            "/api/v1/org/domains",
            json={"domain": "mmnexus.co.za", "is_primary": True},
            headers=_auth_headers(org_admin_user),
        )
        r = client.patch(
            f"/api/v1/hr/employees/{emp['id']}",
            json={"email": "someone@gmail.com"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400


class TestOrgChart:
    def test_org_chart_reflects_manager_hierarchy(self, client: TestClient, token: str):
        manager = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Carol", "last_name": "Boss", "gross_salary": "40000"},
            headers=auth(token),
        ).json()
        report = client.post(
            "/api/v1/hr/employees",
            json={
                "first_name": "Dave",
                "last_name": "Report",
                "gross_salary": "20000",
                "manager_id": manager["id"],
            },
            headers=auth(token),
        ).json()
        assert report["manager_id"] == manager["id"]
        assert report["manager_name"] == "Carol Boss"

        r = client.get("/api/v1/hr/employees/org-chart", headers=auth(token))
        assert r.status_code == 200
        nodes = {n["id"]: n for n in r.json()}
        assert nodes[report["id"]]["manager_id"] == manager["id"]
        assert nodes[manager["id"]]["manager_id"] is None

    def test_employee_cannot_be_own_manager(self, client: TestClient, token: str):
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Eve", "last_name": "Solo", "gross_salary": "20000"},
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/employees/{emp['id']}",
            json={"manager_id": emp["id"]},
            headers=auth(token),
        )
        assert r.status_code == 400

    def test_manager_cycle_rejected(self, client: TestClient, token: str):
        a = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "A", "last_name": "One", "gross_salary": "20000"},
            headers=auth(token),
        ).json()
        b = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "B", "last_name": "Two", "gross_salary": "20000", "manager_id": a["id"]},
            headers=auth(token),
        ).json()

        # A reports to B would close the loop (A -> B -> A).
        r = client.patch(
            f"/api/v1/hr/employees/{a['id']}",
            json={"manager_id": b["id"]},
            headers=auth(token),
        )
        assert r.status_code == 400


# ── Leave ────────────────────────────────────────────────────────────────────

class TestLeave:
    @pytest.fixture
    def employee_id(self, client: TestClient, token: str) -> str:
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Leave", "last_name": "Tester", "gross_salary": "20000"},
            headers=auth(token),
        ).json()
        return emp["id"]

    def test_list_leave_types_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/hr/leave-types", headers=auth(token))
        assert r.status_code == 200

    def test_create_leave_type(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/hr/leave-types",
            json={"name": "Annual Leave", "default_days": "21", "is_paid": True},
            headers=auth(token),
        )
        assert r.status_code == 201
        assert r.json()["name"] == "Annual Leave"

    def test_create_leave_request(self, client: TestClient, token: str, employee_id: str):
        r = client.post(
            "/api/v1/hr/leave-requests",
            json={
                "employee_id": employee_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-05",
                "days_requested": "5",
            },
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "pending"
        assert float(data["days_requested"]) == 5.0

    def test_approve_leave_request(self, client: TestClient, token: str, employee_id: str):
        req = client.post(
            "/api/v1/hr/leave-requests",
            json={
                "employee_id": employee_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-03",
                "days_requested": "3",
            },
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/leave-requests/{req['id']}/status",
            json={"status": "approved"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        assert r.json()["approved_at"] is not None

    def test_reject_leave_request(self, client: TestClient, token: str, employee_id: str):
        req = client.post(
            "/api/v1/hr/leave-requests",
            json={
                "employee_id": employee_id,
                "start_date": "2026-08-01",
                "end_date": "2026-08-02",
                "days_requested": "2",
            },
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/leave-requests/{req['id']}/status",
            json={"status": "rejected", "notes": "Understaffed period"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"


# ── Payroll ──────────────────────────────────────────────────────────────────

class TestPayroll:
    def test_generate_payroll(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Pay", "last_name": "Test", "gross_salary": "30000", "salary_type": "monthly"},
            headers=auth(token),
        )
        r = client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2026, "period_month": 5},
            headers=auth(token),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["period_year"] == 2026
        assert data["period_month"] == 5
        assert data["status"] == "draft"
        assert len(data["payslips"]) == 1
        assert float(data["payslips"][0]["gross_pay"]) == 30000.0
        assert float(data["payslips"][0]["uif_deduction"]) <= 177.12

    def test_generate_payroll_duplicate_fails(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Dup", "last_name": "Test", "gross_salary": "20000"},
            headers=auth(token),
        )
        client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2026, "period_month": 6},
            headers=auth(token),
        )
        r = client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2026, "period_month": 6},
            headers=auth(token),
        )
        assert r.status_code == 409

    def test_list_payroll_periods(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "List", "last_name": "Test", "gross_salary": "22000"},
            headers=auth(token),
        )
        client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2026, "period_month": 4},
            headers=auth(token),
        )
        r = client.get("/api/v1/hr/payroll", headers=auth(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_approve_payroll(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Appr", "last_name": "Test", "gross_salary": "18000"},
            headers=auth(token),
        )
        period = client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2026, "period_month": 3},
            headers=auth(token),
        ).json()
        r = client.patch(
            f"/api/v1/hr/payroll/{period['id']}/approve",
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_uif_capped_at_max(self, client: TestClient, token: str):
        """UIF should be capped at R177.12 regardless of salary."""
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "High", "last_name": "Earner", "gross_salary": "100000"},
            headers=auth(token),
        )
        period = client.post(
            "/api/v1/hr/payroll/generate",
            json={"period_year": 2025, "period_month": 12},
            headers=auth(token),
        ).json()
        slip = period["payslips"][0]
        assert float(slip["uif_deduction"]) == 177.12
