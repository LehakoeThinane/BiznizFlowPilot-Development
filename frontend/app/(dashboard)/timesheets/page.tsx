"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { HRSubNav } from "@/components/HRSubNav";

const PAGE_SIZE = 20;
const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;

interface Employee { id: string; full_name: string }
interface EmployeeListResponse { items: Employee[]; total: number }

interface TimesheetOut {
  id: string; employee_id: string; employee_name: string;
  work_date: string; hours_worked: number; notes: string | null;
}
interface TimesheetListResponse { items: TimesheetOut[]; total: number; skip: number; limit: number }

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-400">{label}</label>
      {children}
    </div>
  );
}

interface LogForm { employee_id: string; work_date: string; hours_worked: string; notes: string }
const EMPTY_FORM: LogForm = { employee_id: "", work_date: new Date().toISOString().slice(0, 10), hours_worked: "", notes: "" };

export default function TimesheetsPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [items, setItems] = useState<TimesheetOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterEmployee, setFilterEmployee] = useState("");
  const [loading, setLoading] = useState(true);

  const [form, setForm] = useState<LogForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadTimesheets = useCallback(() => {
    setLoading(true);
    apiRequest<TimesheetListResponse>("/api/v1/hr/timesheets", {
      query: { skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE, employee_id: filterEmployee || undefined },
    })
      .then((d) => { setItems(d.items); setTotal(d.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, filterEmployee]);

  useEffect(() => {
    apiRequest<EmployeeListResponse>("/api/v1/hr/employees?skip=0&limit=1000")
      .then((d) => setEmployees(d.items ?? []))
      .catch(console.error);
  }, []);

  useEffect(() => { loadTimesheets(); }, [loadTimesheets]);

  async function submitLog(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/v1/hr/timesheets", {
        method: "POST",
        body: {
          employee_id: form.employee_id,
          work_date: form.work_date,
          hours_worked: Number(form.hours_worked),
          notes: form.notes || null,
        },
      });
      setForm((f) => ({ ...EMPTY_FORM, employee_id: f.employee_id }));
      loadTimesheets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log hours.");
    } finally {
      setSaving(false);
    }
  }

  async function removeTimesheet(id: string) {
    await apiRequest(`/api/v1/hr/timesheets/${id}`, { method: "DELETE" });
    loadTimesheets();
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      <PageHeader title="Timesheets" subtitle="Hours worked, for hourly-rate employees' payroll" />

      <div className="erp-panel px-5 py-4">
        <p className="mb-3 text-sm font-semibold text-slate-300">Log hours</p>
        <form onSubmit={submitLog} className="grid grid-cols-5 items-end gap-3">
          {error && <p className="col-span-5 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{error}</p>}
          <Field label="Employee">
            <select
              required
              value={form.employee_id}
              onChange={(e) => setForm((f) => ({ ...f, employee_id: e.target.value }))}
              className={SELECT}
            >
              <option value="">Select…</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </Field>
          <Field label="Date">
            <input
              type="date" required
              value={form.work_date}
              onChange={(e) => setForm((f) => ({ ...f, work_date: e.target.value }))}
              className={INPUT}
            />
          </Field>
          <Field label="Hours">
            <input
              type="number" step="0.25" required
              value={form.hours_worked}
              onChange={(e) => setForm((f) => ({ ...f, hours_worked: e.target.value }))}
              className={INPUT}
            />
          </Field>
          <Field label="Notes (optional)">
            <input
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              className={INPUT}
            />
          </Field>
          <button type="submit" disabled={saving} className="erp-button-primary px-4 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
            {saving ? "Logging…" : "Log hours"}
          </button>
        </form>
      </div>

      <div className="erp-panel">
        <div className="flex items-center justify-between border-b border-white/6 px-5 py-3">
          <p className="text-sm font-semibold text-slate-300">Entries</p>
          <select
            value={filterEmployee}
            onChange={(e) => { setFilterEmployee(e.target.value); setPage(1); }}
            className={`${SELECT} w-56`}
          >
            <option value="">All employees</option>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
          </select>
        </div>
        {loading ? (
          <div className="px-5 py-6 text-sm text-slate-400">Loading…</div>
        ) : items.length === 0 ? (
          <p className="px-5 py-6 text-xs text-slate-500">No hours logged yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/4 text-left text-xs text-slate-500">
                <th className="px-5 py-2.5 font-medium">Employee</th>
                <th className="px-3 py-2.5 font-medium">Date</th>
                <th className="px-3 py-2.5 text-right font-medium">Hours</th>
                <th className="px-3 py-2.5 font-medium">Notes</th>
                <th className="px-5 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/4">
              {items.map((ts) => (
                <tr key={ts.id} className="hover:bg-white/2">
                  <td className="px-5 py-3 font-medium text-white">{ts.employee_name}</td>
                  <td className="px-3 py-3 text-slate-400">{ts.work_date}</td>
                  <td className="px-3 py-3 text-right text-slate-400">{ts.hours_worked}</td>
                  <td className="px-3 py-3 text-slate-400">{ts.notes || "—"}</td>
                  <td className="px-5 py-3 text-right">
                    <button type="button" onClick={() => removeTimesheet(ts.id)} className="text-xs text-slate-400 hover:text-rose-400">
                      Remove
                    </button>
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
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => p + 1)}
        />
      </div>
    </div>
  );
}
