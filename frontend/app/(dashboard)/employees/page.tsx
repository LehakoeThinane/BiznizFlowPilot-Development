"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { OrgChart } from "@/components/OrgChart";
import { HRSubNav } from "@/components/HRSubNav";
import type { OrgChartNode } from "@/types/api";

const PAGE_SIZE = 20;

interface Department { id: string; name: string; description: string | null; employee_count: number }
interface Employee {
  id: string; full_name: string; first_name: string; last_name: string;
  email: string | null; phone: string | null; position: string | null;
  employment_type: string; salary_type: string; gross_salary: number;
  department_id: string | null; department_name: string | null;
  manager_id: string | null; manager_name: string | null; user_id: string | null;
  is_active: boolean; start_date: string | null;
}
interface EmployeeListResponse { items: Employee[]; total: number }
interface BusinessUser { id: string; first_name: string; last_name: string; email: string }
interface UserListResponse { items: BusinessUser[]; total: number }

const EMPLOYMENT_TYPES = ["full_time", "part_time", "contractor", "intern"];
const SALARY_TYPES = ["monthly", "annual", "hourly"];

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency: "ZAR", maximumFractionDigits: 0,
  }).format(n);
}
function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}
function badge(type: string) {
  const m: Record<string, string> = {
    full_time: "bg-emerald-500/20 text-emerald-300",
    part_time: "bg-blue-500/20 text-blue-300",
    contractor: "bg-orange-500/20 text-orange-300",
    intern:    "bg-violet-500/20 text-violet-300",
  };
  return m[type] ?? "bg-white/10 text-slate-300";
}

const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-400">{label}</label>
      {children}
      {error && <p className="mt-1 text-[11px] text-rose-400">{error}</p>}
    </div>
  );
}
function XIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

interface EmployeeForm {
  first_name: string; last_name: string; email: string; phone: string;
  position: string; department_id: string; manager_id: string; employment_type: string;
  salary_type: string; gross_salary: string; start_date: string; notes: string; user_id: string;
}
const EMPTY_FORM: EmployeeForm = {
  first_name: "", last_name: "", email: "", phone: "",
  position: "", department_id: "", manager_id: "", employment_type: "full_time",
  salary_type: "monthly", gross_salary: "", start_date: "", notes: "", user_id: "",
};
function empToForm(e: Employee): EmployeeForm {
  return {
    first_name: e.first_name, last_name: e.last_name,
    email: e.email ?? "", phone: e.phone ?? "",
    position: e.position ?? "", department_id: e.department_id ?? "",
    manager_id: e.manager_id ?? "",
    employment_type: e.employment_type, salary_type: e.salary_type,
    gross_salary: String(e.gross_salary), start_date: e.start_date ?? "", notes: "",
    user_id: e.user_id ?? "",
  };
}

interface DeptForm { name: string; description: string }
const EMPTY_DEPT: DeptForm = { name: "", description: "" };

type ActiveTab = "employees" | "departments" | "org-chart";

export default function EmployeesPage() {
  const [tab, setTab] = useState<ActiveTab>("employees");

  // ── Employees state ────────────────────────────────────────────────────────
  const [employees, setEmployees]   = useState<Employee[]>([]);
  const [total, setTotal]           = useState(0);
  const [page, setPage]             = useState(1);
  const [loading, setLoading]       = useState(true);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [users, setUsers]           = useState<BusinessUser[]>([]);

  // ── Headcount & Demographics state ─────────────────────────────────────────
  const [allEmployees, setAllEmployees] = useState<Employee[]>([]);
  const [demographicsLoading, setDemographicsLoading] = useState(true);

  // ── Org chart state ────────────────────────────────────────────────────────
  const [orgChartNodes, setOrgChartNodes] = useState<OrgChartNode[]>([]);
  const [orgChartLoading, setOrgChartLoading] = useState(false);
  const [orgChartLoaded, setOrgChartLoaded] = useState(false);

  const [showAddModal, setShowAddModal]   = useState(false);
  const [editTarget, setEditTarget]       = useState<Employee | null>(null);
  const [deleteTarget, setDeleteTarget]   = useState<Employee | null>(null);
  const [form, setForm]                   = useState<EmployeeForm>(EMPTY_FORM);
  const [saving, setSaving]               = useState(false);
  const [errors, setErrors]               = useState<Partial<EmployeeForm>>({});
  const [serverError, setServerError]     = useState("");
  const [deleting, setDeleting]           = useState(false);

  // ── Departments state ──────────────────────────────────────────────────────
  const [deptLoading, setDeptLoading]     = useState(false);
  const [showDeptModal, setShowDeptModal] = useState(false);
  const [editDept, setEditDept]           = useState<Department | null>(null);
  const [deptForm, setDeptForm]           = useState<DeptForm>(EMPTY_DEPT);
  const [deptSaving, setDeptSaving]       = useState(false);
  const [deptServerError, setDeptServerError] = useState("");

  const token = getStoredToken();

  const loadEmployees = useCallback(() => {
    setLoading(true);
    const skip = (page - 1) * PAGE_SIZE;
    apiRequest<EmployeeListResponse>(`/api/v1/hr/employees?skip=${skip}&limit=${PAGE_SIZE}`, { authToken: token })
      .then((d) => { setEmployees(d.items ?? []); setTotal(d.total ?? 0); })
      .catch(console.error).finally(() => setLoading(false));
  }, [token, page]);

  const loadDepartments = useCallback(() => {
    setDeptLoading(true);
    apiRequest<Department[]>("/api/v1/hr/departments", { authToken: token })
      .then(setDepartments).catch(console.error).finally(() => setDeptLoading(false));
  }, [token]);

  const loadUsers = useCallback(() => {
    apiRequest<UserListResponse>("/api/v1/users?limit=200", { authToken: token })
      .then((d) => setUsers(d.items ?? []))
      .catch(console.error);
  }, [token]);

  useEffect(() => { loadEmployees(); loadDepartments(); loadUsers(); }, [loadEmployees, loadDepartments, loadUsers]);

  useEffect(() => {
    setDemographicsLoading(true);
    apiRequest<EmployeeListResponse>("/api/v1/hr/employees?skip=0&limit=1000", { authToken: token })
      .then((d) => setAllEmployees(d.items ?? []))
      .catch(console.error)
      .finally(() => setDemographicsLoading(false));
  }, [token]);

  const [nowMs] = useState(() => Date.now());

  const demographics = useMemo(() => {
    const activeEmployees = allEmployees.filter((e) => e.is_active);
    const inactiveCount = allEmployees.length - activeEmployees.length;

    const byType = new Map<string, number>();
    for (const e of allEmployees) byType.set(e.employment_type, (byType.get(e.employment_type) ?? 0) + 1);
    const typeBreakdown = EMPLOYMENT_TYPES
      .map((t) => ({ type: t, count: byType.get(t) ?? 0 }))
      .filter((t) => t.count > 0);

    const deptBreakdown = [...departments]
      .sort((a, b) => b.employee_count - a.employee_count)
      .slice(0, 6);

    const tenureDays = activeEmployees
      .filter((e) => e.start_date)
      .map((e) => (nowMs - new Date(e.start_date as string).getTime()) / 86_400_000);
    const avgTenureYears = tenureDays.length > 0
      ? tenureDays.reduce((s, d) => s + d, 0) / tenureDays.length / 365
      : null;

    return {
      total: allEmployees.length,
      active: activeEmployees.length,
      inactive: inactiveCount,
      typeBreakdown,
      deptBreakdown,
      avgTenureYears,
    };
  }, [allEmployees, departments, nowMs]);

  useEffect(() => {
    if (tab !== "org-chart" || orgChartLoaded) return;
    setOrgChartLoading(true);
    apiRequest<OrgChartNode[]>("/api/v1/hr/employees/org-chart", { authToken: token })
      .then((d) => { setOrgChartNodes(d ?? []); setOrgChartLoaded(true); })
      .catch(console.error).finally(() => setOrgChartLoading(false));
  }, [tab, orgChartLoaded, token]);

  function set(field: keyof EmployeeForm, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  }

  function validate(): boolean {
    const e: Partial<EmployeeForm> = {};
    if (!form.first_name.trim()) e.first_name = "Required";
    if (!form.last_name.trim())  e.last_name  = "Required";
    if (!form.gross_salary || isNaN(Number(form.gross_salary))) e.gross_salary = "Must be a number";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true); setServerError("");
    try {
      const body: Record<string, unknown> = {
        first_name: form.first_name.trim(), last_name: form.last_name.trim(),
        employment_type: form.employment_type, salary_type: form.salary_type,
        gross_salary: Number(form.gross_salary),
      };
      if (form.email)         body.email         = form.email.trim();
      if (form.phone)         body.phone         = form.phone.trim();
      if (form.position)      body.position      = form.position.trim();
      if (form.department_id) body.department_id = form.department_id;
      if (form.manager_id)    body.manager_id    = form.manager_id;
      if (form.start_date)    body.start_date    = form.start_date;
      if (form.notes)         body.notes         = form.notes.trim();
      if (form.user_id)       body.user_id       = form.user_id;

      if (editTarget) {
        await apiRequest(`/api/v1/hr/employees/${editTarget.id}`, { method: "PATCH", body, authToken: token });
        setEditTarget(null);
      } else {
        await apiRequest("/api/v1/hr/employees", { method: "POST", body, authToken: token });
        setShowAddModal(false);
      }
      setForm(EMPTY_FORM); loadEmployees(); setOrgChartLoaded(false);
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : "Failed to save employee.");
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiRequest(`/api/v1/hr/employees/${deleteTarget.id}`, { method: "DELETE", authToken: token });
      setDeleteTarget(null); loadEmployees();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete employee.");
    } finally { setDeleting(false); }
  }

  async function submitDept(e: React.FormEvent) {
    e.preventDefault();
    if (!deptForm.name.trim()) return;
    setDeptSaving(true); setDeptServerError("");
    try {
      const body: Record<string, unknown> = { name: deptForm.name.trim() };
      if (deptForm.description) body.description = deptForm.description.trim();
      if (editDept) {
        await apiRequest(`/api/v1/hr/departments/${editDept.id}`, { method: "PATCH", body, authToken: token });
        setEditDept(null);
      } else {
        await apiRequest("/api/v1/hr/departments", { method: "POST", body, authToken: token });
        setShowDeptModal(false);
      }
      setDeptForm(EMPTY_DEPT); loadDepartments();
    } catch (err: unknown) {
      setDeptServerError(err instanceof Error ? err.message : "Failed to save department.");
    } finally { setDeptSaving(false); }
  }

  const linkableUsers = useMemo(() => {
    const linkedElsewhere = new Set(
      allEmployees.filter((e) => e.user_id && e.id !== editTarget?.id).map((e) => e.user_id)
    );
    return users.filter((u) => !linkedElsewhere.has(u.id));
  }, [users, allEmployees, editTarget]);

  const active       = employees.filter((e) => e.is_active).length;
  const totalPayroll = employees.filter((e) => e.is_active).reduce((s, e) => s + Number(e.gross_salary), 0);
  const isModalOpen  = showAddModal || editTarget !== null;

  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      {/* ── Header ────────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <PageHeader title="Employees & Departments" subtitle={`${total} employees · ${departments.length} departments`} />
        {tab === "employees" && (
          <button
            type="button"
            onClick={() => { setShowAddModal(true); setForm(EMPTY_FORM); setErrors({}); setServerError(""); }}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors"
          >
            + Add Employee
          </button>
        )}
        {tab === "departments" && (
          <button
            type="button"
            onClick={() => { setShowDeptModal(true); setDeptForm(EMPTY_DEPT); setDeptServerError(""); }}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors"
          >
            + Add Department
          </button>
        )}
      </div>

      {/* ── Headcount & Demographics ─────────────────────────────────────────── */}
      <div className="erp-panel p-5">
        <p className="mb-4 text-sm font-semibold text-slate-300">Headcount & Demographics</p>
        {demographicsLoading ? (
          <div className="text-sm text-slate-400">Loading…</div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="grid grid-cols-3 gap-3 lg:col-span-1 lg:grid-cols-1">
              <div className="rounded-lg bg-white/4 p-3">
                <p className="text-[11px] font-medium text-slate-400">Total Headcount</p>
                <p className="mt-1 text-xl font-bold text-white">{demographics.total}</p>
              </div>
              <div className="rounded-lg bg-white/4 p-3">
                <p className="text-[11px] font-medium text-slate-400">Active / Inactive</p>
                <p className="mt-1 text-xl font-bold text-white">
                  <span className="text-emerald-400">{demographics.active}</span>
                  <span className="text-slate-500"> / </span>
                  <span className="text-slate-400">{demographics.inactive}</span>
                </p>
              </div>
              <div className="rounded-lg bg-white/4 p-3">
                <p className="text-[11px] font-medium text-slate-400">Avg. Tenure</p>
                <p className="mt-1 text-xl font-bold text-white">
                  {demographics.avgTenureYears === null ? "—" : `${demographics.avgTenureYears.toFixed(1)} yrs`}
                </p>
              </div>
            </div>

            <div className="lg:col-span-1">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">By Department</p>
              {demographics.deptBreakdown.length === 0 ? (
                <p className="text-xs text-slate-500">No departments yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {demographics.deptBreakdown.map((d) => (
                    <div key={d.id} className="flex items-center justify-between gap-3">
                      <span className="truncate text-xs text-slate-300">{d.name}</span>
                      <span className="shrink-0 text-xs font-medium text-slate-400">{d.employee_count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="lg:col-span-1">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">By Employment Type</p>
              {demographics.typeBreakdown.length === 0 ? (
                <p className="text-xs text-slate-500">No employees yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {demographics.typeBreakdown.map((t) => (
                    <div key={t.type} className="flex items-center justify-between gap-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badge(t.type)}`}>
                        {t.type.replace("_", " ")}
                      </span>
                      <span className="shrink-0 text-xs font-medium text-slate-400">{t.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Tab switcher ─────────────────────────────────────────────────────── */}
      <div className="flex gap-2">
        {(["employees", "departments", "org-chart"] as ActiveTab[]).map((t) => (
          <button
            key={t} type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium capitalize transition-colors ${
              tab === t ? "bg-blue-600 text-white" : "bg-white/4 text-slate-400 hover:bg-white/8"
            }`}
          >
            {t === "org-chart" ? "Org Chart" : t}
          </button>
        ))}
      </div>

      {/* ── Employees tab ─────────────────────────────────────────────────────── */}
      {tab === "employees" && (
        <>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Total Employees", value: String(total),     color: "bg-blue-500" },
              { label: "Active",          value: String(active),    color: "bg-emerald-500" },
              { label: "Monthly Payroll", value: fmt(totalPayroll), color: "bg-violet-500" },
            ].map((c) => (
              <div key={c.label} className="erp-panel p-5">
                <span className={`status-dot ${c.color} ${c.color.replace("bg-", "text-")}`} />
                <p className="text-xs font-medium text-slate-400">{c.label}</p>
                <p className="mt-1.5 text-2xl font-bold text-white">{c.value}</p>
              </div>
            ))}
          </div>

          <div className="erp-panel">
            <div className="border-b border-outline-variant/80 px-5 py-3">
              <p className="text-sm font-semibold text-slate-300">All Employees</p>
            </div>
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
            ) : employees.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-slate-500">
                No employees yet. Click <strong className="text-white">+ Add Employee</strong> to get started.
              </div>
            ) : (
              <div className="divide-y divide-outline-variant/60">
                {employees.map((emp) => (
                  <div key={emp.id} className="flex items-center gap-4 px-5 py-3.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                      {initials(emp.full_name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white">{emp.full_name}</p>
                      <p className="truncate text-xs text-slate-500">
                        {emp.position ?? "—"} · {emp.department_name ?? "No department"}
                        {emp.email ? ` · ${emp.email}` : ""}
                      </p>
                    </div>
                    {!emp.user_id && emp.is_active && (
                      <span className="shrink-0 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                        No login
                      </span>
                    )}
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${badge(emp.employment_type)}`}>
                      {emp.employment_type.replace("_", " ")}
                    </span>
                    <p className="shrink-0 text-sm text-slate-400">{fmt(Number(emp.gross_salary))}</p>
                    <span className={`h-2 w-2 shrink-0 rounded-full ${emp.is_active ? "bg-emerald-400" : "bg-slate-600"}`} />
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        onClick={() => { setEditTarget(emp); setForm(empToForm(emp)); setErrors({}); setServerError(""); }}
                        className="rounded-md bg-white/5 px-2 py-1 text-[11px] text-slate-400 hover:text-white transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(emp)}
                        className="rounded-md bg-rose-500/10 px-2 py-1 text-[11px] text-rose-400 hover:bg-rose-500/20 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Pagination
              page={page}
              totalPages={Math.max(1, Math.ceil(total / PAGE_SIZE))}
              totalItems={total}
              pageSize={PAGE_SIZE}
              onPrev={() => setPage((p) => p - 1)}
              onNext={() => setPage((p) => p + 1)}
            />
          </div>
        </>
      )}

      {/* ── Departments tab ───────────────────────────────────────────────────── */}
      {tab === "departments" && (
        <div className="erp-panel">
          <div className="border-b border-outline-variant/80 px-5 py-3">
            <p className="text-sm font-semibold text-slate-300">All Departments</p>
          </div>
          {deptLoading ? (
            <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
          ) : departments.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-slate-500">
              No departments yet. Click <strong className="text-white">+ Add Department</strong>.
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/60">
              {departments.map((dept) => (
                <div key={dept.id} className="flex items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white">{dept.name}</p>
                    {dept.description && <p className="text-xs text-slate-500">{dept.description}</p>}
                  </div>
                  <span className="shrink-0 rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-medium text-blue-300">
                    {dept.employee_count} {dept.employee_count === 1 ? "employee" : "employees"}
                  </span>
                  <button
                    type="button"
                    onClick={() => { setEditDept(dept); setDeptForm({ name: dept.name, description: dept.description ?? "" }); setDeptServerError(""); setShowDeptModal(true); }}
                    className="shrink-0 rounded-md bg-white/5 px-2 py-1 text-[11px] text-slate-400 hover:text-white transition-colors"
                  >
                    Edit
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Org Chart tab ─────────────────────────────────────────────────────── */}
      {tab === "org-chart" && (
        <div className="erp-panel">
          <div className="border-b border-outline-variant/80 px-5 py-3">
            <p className="text-sm font-semibold text-slate-300">Reporting Structure</p>
          </div>
          <div className="h-[600px]">
            {orgChartLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">Loading…</div>
            ) : (
              <OrgChart nodes={orgChartNodes} />
            )}
          </div>
        </div>
      )}

      {/* ── Add / Edit Employee Modal ─────────────────────────────────────────── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">
                {editTarget ? "Edit Employee" : "Add Employee"}
              </h2>
              <button
                type="button" aria-label="Close"
                onClick={() => { setShowAddModal(false); setEditTarget(null); }}
                className="text-slate-400 hover:text-white"
              >
                <XIcon />
              </button>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <div className="max-h-[70vh] overflow-y-auto px-6 py-5">
                <div className="grid grid-cols-2 gap-4">
                  <Field label="First Name *" error={errors.first_name}>
                    <input className={INPUT} value={form.first_name} onChange={(e) => set("first_name", e.target.value)} placeholder="e.g. Thabo" />
                  </Field>
                  <Field label="Last Name *" error={errors.last_name}>
                    <input className={INPUT} value={form.last_name} onChange={(e) => set("last_name", e.target.value)} placeholder="e.g. Mokoena" />
                  </Field>
                  <Field label="Email">
                    <input type="email" className={INPUT} value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="thabo@company.com" />
                  </Field>
                  <Field label="Phone">
                    <input className={INPUT} value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+27 71 234 5678" />
                  </Field>
                  <Field label="Position / Job Title">
                    <input className={INPUT} value={form.position} onChange={(e) => set("position", e.target.value)} placeholder="e.g. Sales Manager" />
                  </Field>
                  <Field label="Department">
                    <select aria-label="Department" className={SELECT} value={form.department_id} onChange={(e) => set("department_id", e.target.value)}>
                      <option value="">No department</option>
                      {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Reports To">
                    <select aria-label="Reports To" className={SELECT} value={form.manager_id} onChange={(e) => set("manager_id", e.target.value)}>
                      <option value="">No manager</option>
                      {employees.filter((e) => e.id !== editTarget?.id).map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Employment Type">
                    <select aria-label="Employment Type" className={SELECT} value={form.employment_type} onChange={(e) => set("employment_type", e.target.value)}>
                      {EMPLOYMENT_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                    </select>
                  </Field>
                  <Field label="Salary Type">
                    <select aria-label="Salary Type" className={SELECT} value={form.salary_type} onChange={(e) => set("salary_type", e.target.value)}>
                      {SALARY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </Field>
                  <Field label="Gross Salary (R) *" error={errors.gross_salary}>
                    <input type="number" min="0" step="100" className={INPUT} value={form.gross_salary} onChange={(e) => set("gross_salary", e.target.value)} placeholder="25000" />
                  </Field>
                  <Field label="Start Date">
                    <input type="date" aria-label="Start date" className={INPUT} value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
                  </Field>
                  <Field label="Linked Account">
                    <select aria-label="Linked Account" className={SELECT} value={form.user_id} onChange={(e) => set("user_id", e.target.value)}>
                      <option value="">No login yet</option>
                      {linkableUsers.map((u) => (
                        <option key={u.id} value={u.id}>{u.first_name} {u.last_name} ({u.email})</option>
                      ))}
                    </select>
                  </Field>
                </div>
                <div className="mt-4">
                  <Field label="Notes">
                    <textarea aria-label="Notes" rows={2} className={`${INPUT} resize-none`} value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Optional notes…" />
                  </Field>
                </div>
                {serverError && (
                  <p className="mt-3 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{serverError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => { setShowAddModal(false); setEditTarget(null); }} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={saving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {saving ? "Saving…" : editTarget ? "Save Changes" : "Add Employee"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation ───────────────────────────────────────────────── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="px-6 py-5">
              <p className="text-base font-semibold text-white">Delete employee?</p>
              <p className="mt-1 text-sm text-slate-400">
                This will permanently remove <strong className="text-white">{deleteTarget.full_name}</strong>. This cannot be undone.
              </p>
            </div>
            <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
              <button type="button" onClick={() => setDeleteTarget(null)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDelete}
                className="rounded-lg bg-rose-600 px-5 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50 transition-colors"
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Add / Edit Department Modal ───────────────────────────────────────── */}
      {(showDeptModal || editDept !== null) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">
                {editDept ? "Edit Department" : "Add Department"}
              </h2>
              <button
                type="button" aria-label="Close"
                onClick={() => { setShowDeptModal(false); setEditDept(null); }}
                className="text-slate-400 hover:text-white"
              >
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitDept} noValidate>
              <div className="space-y-4 px-6 py-5">
                <Field label="Name *">
                  <input
                    className={INPUT}
                    value={deptForm.name}
                    onChange={(e) => setDeptForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g. Engineering"
                  />
                </Field>
                <Field label="Description">
                  <input
                    className={INPUT}
                    value={deptForm.description}
                    onChange={(e) => setDeptForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Optional description"
                  />
                </Field>
                {deptServerError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{deptServerError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => { setShowDeptModal(false); setEditDept(null); }} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={deptSaving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {deptSaving ? "Saving…" : editDept ? "Save Changes" : "Add Department"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

