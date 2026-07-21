"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { HRSubNav } from "@/components/HRSubNav";

const PAGE_SIZE = 20;

interface Employee   { id: string; full_name: string }
interface LeaveType  { id: string; name: string; default_days: number; is_paid: boolean }
interface LeaveRequest {
  id: string; employee_id: string; employee_name: string;
  leave_type_id: string | null; leave_type_name: string | null;
  start_date: string; end_date: string; days_requested: number;
  status: string; reason: string | null; approved_at: string | null;
}
interface LeaveListResponse { items: LeaveRequest[]; total: number }

type ActiveTab = "requests" | "types";
const STATUS_FILTERS = ["all", "pending", "approved", "rejected", "cancelled"];

function statusColor(s: string) {
  if (s === "approved")  return "bg-emerald-500/20 text-emerald-300";
  if (s === "rejected")  return "bg-rose-500/20 text-rose-300";
  if (s === "pending")   return "bg-orange-500/20 text-orange-300";
  if (s === "cancelled") return "bg-slate-500/30 text-slate-400";
  return "bg-white/10 text-slate-300";
}

const INPUT  = "w-full rounded-lg border border-white/10 bg-[#0f172a] px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f172a] [&>option]:text-white`;

function Field({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) {
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

interface LeaveForm {
  employee_id: string; leave_type_id: string;
  start_date: string; end_date: string; days_requested: string; reason: string;
}
const EMPTY: LeaveForm = { employee_id: "", leave_type_id: "", start_date: "", end_date: "", days_requested: "", reason: "" };

interface LeaveTypeForm { name: string; default_days: string; is_paid: boolean }
const EMPTY_TYPE: LeaveTypeForm = { name: "", default_days: "21", is_paid: true };

export default function LeavePage() {
  const [tab, setTab] = useState<ActiveTab>("requests");

  // ── Leave requests state ───────────────────────────────────────────────────
  const [requests, setRequests]   = useState<LeaveRequest[]>([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(1);
  const [filter, setFilter]       = useState("all");
  const [loading, setLoading]     = useState(true);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);

  const [showModal, setShowModal] = useState(false);
  const [form, setForm]           = useState<LeaveForm>(EMPTY);
  const [errors, setErrors]       = useState<Partial<LeaveForm>>({});
  const [saving, setSaving]       = useState(false);
  const [serverError, setServerError] = useState("");

  // ── Leave types state ──────────────────────────────────────────────────────
  const [typesLoading, setTypesLoading] = useState(false);
  const [showTypeModal, setShowTypeModal] = useState(false);
  const [typeForm, setTypeForm]           = useState<LeaveTypeForm>(EMPTY_TYPE);
  const [typeSaving, setTypeSaving]       = useState(false);
  const [typeServerError, setTypeServerError] = useState("");

  const token = getStoredToken();

  const loadRequests = useCallback(() => {
    setLoading(true);
    const skip = (page - 1) * PAGE_SIZE;
    const qs = filter !== "all" ? `&status=${filter}` : "";
    apiRequest<LeaveListResponse>(`/api/v1/hr/leave-requests?skip=${skip}&limit=${PAGE_SIZE}${qs}`, { authToken: token })
      .then((d) => { setRequests(d.items ?? []); setTotal(d.total ?? 0); })
      .catch(console.error).finally(() => setLoading(false));
  }, [token, filter, page]);

  const loadLeaveTypes = useCallback(() => {
    setTypesLoading(true);
    apiRequest<LeaveType[]>("/api/v1/hr/leave-types", { authToken: token })
      .then(setLeaveTypes).catch(console.error).finally(() => setTypesLoading(false));
  }, [token]);

  useEffect(() => { loadRequests(); }, [loadRequests]);

  useEffect(() => {
    apiRequest<{ items: Employee[] }>("/api/v1/hr/employees?limit=100", { authToken: token })
      .then((d) => setEmployees(d.items ?? [])).catch(() => null);
    loadLeaveTypes();
  }, [token, loadLeaveTypes]);

  function set(field: keyof LeaveForm, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  }

  useEffect(() => {
    if (!form.start_date || !form.end_date) return;
    const start = new Date(form.start_date);
    const end = new Date(form.end_date);
    if (isNaN(start.getTime()) || isNaN(end.getTime()) || end < start) return;
    const days = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
    setForm((f) => ({ ...f, days_requested: String(days) }));
    setErrors((e) => ({ ...e, days_requested: undefined }));
  }, [form.start_date, form.end_date]);

  function validate(): boolean {
    const e: Partial<LeaveForm> = {};
    if (!form.employee_id)   e.employee_id   = "Required";
    if (!form.start_date)    e.start_date    = "Required";
    if (!form.end_date)      e.end_date      = "Required";
    if (!form.days_requested || isNaN(Number(form.days_requested))) e.days_requested = "Must be a number";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true); setServerError("");
    try {
      const body: Record<string, unknown> = {
        employee_id: form.employee_id, start_date: form.start_date,
        end_date: form.end_date, days_requested: Number(form.days_requested),
      };
      if (form.leave_type_id) body.leave_type_id = form.leave_type_id;
      if (form.reason)        body.reason        = form.reason.trim();
      await apiRequest("/api/v1/hr/leave-requests", { method: "POST", body, authToken: token });
      setShowModal(false); setForm(EMPTY); loadRequests();
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : "Failed to submit leave request.");
    } finally { setSaving(false); }
  }

  async function updateStatus(id: string, status: string) {
    try {
      await apiRequest(`/api/v1/hr/leave-requests/${id}/status`, {
        method: "PATCH", body: { status }, authToken: token,
      });
      loadRequests();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to update status.");
    }
  }

  async function submitLeaveType(e: React.FormEvent) {
    e.preventDefault();
    if (!typeForm.name.trim()) return;
    setTypeSaving(true); setTypeServerError("");
    try {
      const body: Record<string, unknown> = {
        name: typeForm.name.trim(),
        default_days: Number(typeForm.default_days) || 0,
        is_paid: typeForm.is_paid,
      };
      await apiRequest("/api/v1/hr/leave-types", { method: "POST", body, authToken: token });
      setShowTypeModal(false); setTypeForm(EMPTY_TYPE); loadLeaveTypes();
    } catch (err: unknown) {
      setTypeServerError(err instanceof Error ? err.message : "Failed to create leave type.");
    } finally { setTypeSaving(false); }
  }

  const pending  = requests.filter((r) => r.status === "pending").length;
  const approved = requests.filter((r) => r.status === "approved").length;

  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      {/* ── Header ────────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <PageHeader title="Leave Management" subtitle={`${total} requests · ${pending} pending`} />
        {tab === "requests" ? (
          <button
            type="button"
            onClick={() => { setShowModal(true); setForm(EMPTY); setErrors({}); setServerError(""); }}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
          >
            + New Request
          </button>
        ) : (
          <button
            type="button"
            onClick={() => { setShowTypeModal(true); setTypeForm(EMPTY_TYPE); setTypeServerError(""); }}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
          >
            + Add Leave Type
          </button>
        )}
      </div>

      {/* ── Tab switcher ─────────────────────────────────────────────────────── */}
      <div className="flex gap-2">
        {(["requests", "types"] as ActiveTab[]).map((t) => (
          <button
            key={t} type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium capitalize transition-colors ${
              tab === t ? "bg-blue-600 text-white" : "bg-white/4 text-slate-400 hover:bg-white/8"
            }`}
          >
            {t === "requests" ? "Leave Requests" : "Leave Types"}
          </button>
        ))}
      </div>

      {/* ── Leave Requests tab ────────────────────────────────────────────────── */}
      {tab === "requests" && (
        <>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Pending",  value: String(pending),  color: "bg-orange-500" },
              { label: "Approved", value: String(approved), color: "bg-emerald-500" },
              { label: "Total",    value: String(total),    color: "bg-blue-500" },
            ].map((c) => (
              <div key={c.label} className="erp-panel p-5">
                <span className={`status-dot ${c.color} ${c.color.replace("bg-", "text-")}`} />
                <p className="text-xs font-medium text-slate-400">{c.label}</p>
                <p className="mt-1.5 text-2xl font-bold text-white">{c.value}</p>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            {STATUS_FILTERS.map((s) => (
              <button
                type="button" key={s}
                onClick={() => { setFilter(s); setPage(1); }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                  filter === s ? "bg-blue-600 text-white" : "bg-white/4 text-slate-400 hover:bg-white/8"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="rounded-xl border border-white/6 bg-[#1e293b]">
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
            ) : requests.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-slate-500">No leave requests found.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/6 text-left text-xs text-slate-500">
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-3 py-3 font-medium">Type</th>
                    <th className="px-3 py-3 font-medium">Period</th>
                    <th className="px-3 py-3 font-medium">Days</th>
                    <th className="px-3 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/4">
                  {requests.map((r) => (
                    <tr key={r.id} className="hover:bg-white/2">
                      <td className="px-5 py-3">
                        <p className="font-medium text-white">{r.employee_name}</p>
                        {r.reason && <p className="max-w-45 truncate text-xs text-slate-500">{r.reason}</p>}
                      </td>
                      <td className="px-3 py-3 text-slate-400">{r.leave_type_name ?? "—"}</td>
                      <td className="px-3 py-3 whitespace-nowrap text-slate-400">
                        {r.start_date} → {r.end_date}
                      </td>
                      <td className="px-3 py-3 text-white">{r.days_requested}</td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusColor(r.status)}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        {r.status === "pending" && (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => updateStatus(r.id, "approved")}
                              className="rounded-md bg-emerald-600/20 px-2 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-600/40 transition-colors"
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              onClick={() => updateStatus(r.id, "rejected")}
                              className="rounded-md bg-rose-600/20 px-2 py-1 text-[11px] font-medium text-rose-300 hover:bg-rose-600/40 transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

      {/* ── Leave Types tab ───────────────────────────────────────────────────── */}
      {tab === "types" && (
        <div className="rounded-xl border border-white/6 bg-[#1e293b]">
          <div className="border-b border-white/6 px-5 py-3">
            <p className="text-sm font-semibold text-slate-300">Leave Types</p>
          </div>
          {typesLoading ? (
            <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
          ) : leaveTypes.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-slate-500">
              No leave types yet. Click <strong className="text-white">+ Add Leave Type</strong> to create one.
            </div>
          ) : (
            <div className="divide-y divide-white/4">
              {leaveTypes.map((lt) => (
                <div key={lt.id} className="flex items-center gap-4 px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white">{lt.name}</p>
                    <p className="text-xs text-slate-500">{lt.default_days} days default</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    lt.is_paid ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-500/30 text-slate-400"
                  }`}>
                    {lt.is_paid ? "Paid" : "Unpaid"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── New Leave Request Modal ───────────────────────────────────────────── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-[#0f172a] shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/8 px-6 py-4">
              <h2 className="text-base font-semibold text-white">New Leave Request</h2>
              <button type="button" aria-label="Close" onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-4 px-6 py-5">
                <Field label="Employee *" error={errors.employee_id}>
                  <select aria-label="Employee" className={SELECT} value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)}>
                    <option value="">Select employee…</option>
                    {employees.map((emp) => <option key={emp.id} value={emp.id}>{emp.full_name}</option>)}
                  </select>
                </Field>
                <Field label="Leave Type">
                  <select aria-label="Leave Type" className={SELECT} value={form.leave_type_id} onChange={(e) => set("leave_type_id", e.target.value)}>
                    <option value="">General / Unspecified</option>
                    {leaveTypes.map((lt) => (
                      <option key={lt.id} value={lt.id}>{lt.name} {lt.is_paid ? "(Paid)" : "(Unpaid)"}</option>
                    ))}
                  </select>
                </Field>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Start Date *" error={errors.start_date}>
                    <input type="date" aria-label="Start date" className={INPUT} value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
                  </Field>
                  <Field label="End Date *" error={errors.end_date}>
                    <input type="date" aria-label="End date" className={INPUT} value={form.end_date} onChange={(e) => set("end_date", e.target.value)} />
                  </Field>
                </div>
                <Field label="Days Requested *" error={errors.days_requested}>
                  <input type="number" min="0.5" step="0.5" className={INPUT} value={form.days_requested} onChange={(e) => set("days_requested", e.target.value)} placeholder="e.g. 3" />
                </Field>
                <Field label="Reason">
                  <textarea aria-label="Reason" rows={3} className={`${INPUT} resize-none`} value={form.reason} onChange={(e) => set("reason", e.target.value)} placeholder="Optional reason…" />
                </Field>
                {serverError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{serverError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors">
                  {saving ? "Submitting…" : "Submit Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Add Leave Type Modal ──────────────────────────────────────────────── */}
      {showTypeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-white/10 bg-[#0f172a] shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/8 px-6 py-4">
              <h2 className="text-base font-semibold text-white">Add Leave Type</h2>
              <button type="button" aria-label="Close" onClick={() => setShowTypeModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitLeaveType} noValidate>
              <div className="space-y-4 px-6 py-5">
                <Field label="Name *">
                  <input
                    className={INPUT}
                    value={typeForm.name}
                    onChange={(e) => setTypeForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g. Annual Leave"
                  />
                </Field>
                <Field label="Default Days">
                  <input
                    aria-label="Default days" type="number" min="0" step="1" className={INPUT}
                    value={typeForm.default_days}
                    onChange={(e) => setTypeForm((f) => ({ ...f, default_days: e.target.value }))}
                  />
                </Field>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox" id="is_paid"
                    checked={typeForm.is_paid}
                    onChange={(e) => setTypeForm((f) => ({ ...f, is_paid: e.target.checked }))}
                    className="h-4 w-4 rounded border-white/20 bg-white/5"
                  />
                  <label htmlFor="is_paid" className="text-sm text-slate-300">Paid leave</label>
                </div>
                {typeServerError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{typeServerError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowTypeModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={typeSaving} className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors">
                  {typeSaving ? "Saving…" : "Add Leave Type"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
