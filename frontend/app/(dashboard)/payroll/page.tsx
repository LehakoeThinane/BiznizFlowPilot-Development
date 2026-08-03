"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { FinanceSubNav } from "@/components/FinanceSubNav";

interface PayslipOut {
  id: string;
  employee_name: string;
  basic_pay: number;
  overtime_pay: number;
  bonus: number;
  gross_pay: number;
  total_deductions: number;
  net_pay: number;
  tax_deduction: number;
  uif_deduction: number;
  other_deductions: number;
  status: string;
}

interface PayrollPeriodOut {
  id: string;
  period_year: number;
  period_month: number;
  status: string;
  total_gross: number;
  total_deductions: number;
  total_net: number;
  processed_at: string | null;
  payslips: PayslipOut[];
}

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const INPUT = "erp-input w-full px-3 py-2 text-sm";

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency: "ZAR", maximumFractionDigits: 0,
  }).format(n);
}

function statusBadge(s: string) {
  if (s === "completed" || s === "finalized") return "bg-emerald-500/20 text-emerald-300";
  if (s === "draft")    return "bg-orange-500/20 text-orange-300";
  return "bg-white/10 text-slate-300";
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-400">{label}</label>
      {children}
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

interface GenerateForm { period_year: string; period_month: string; notes: string }
const EMPTY_GENERATE: GenerateForm = {
  period_year: String(new Date().getFullYear()),
  period_month: String(new Date().getMonth() + 1),
  notes: "",
};

interface AdjustForm { overtime_pay: string; bonus: string; other_deductions: string }

export default function PayrollPage() {
  const [periods, setPeriods] = useState<PayrollPeriodOut[]>([]);
  const [selected, setSelected] = useState<PayrollPeriodOut | null>(null);
  const [loading, setLoading] = useState(true);

  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generateForm, setGenerateForm] = useState<GenerateForm>(EMPTY_GENERATE);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");

  const [approving, setApproving] = useState(false);

  const [editTarget, setEditTarget] = useState<PayslipOut | null>(null);
  const [adjustForm, setAdjustForm] = useState<AdjustForm>({ overtime_pay: "0", bonus: "0", other_deductions: "0" });
  const [adjustSaving, setAdjustSaving] = useState(false);
  const [adjustError, setAdjustError] = useState("");

  function loadPeriods(selectId?: string) {
    apiRequest<PayrollPeriodOut[]>("/api/v1/hr/payroll")
      .then((d) => {
        setPeriods(d);
        const target = selectId ? d.find((p) => p.id === selectId) : d[0];
        if (target) loadPeriod(target.id);
        else { setSelected(null); setLoading(false); }
      })
      .catch(console.error);
  }

  function loadPeriod(id: string) {
    setLoading(true);
    apiRequest<PayrollPeriodOut>(`/api/v1/hr/payroll/${id}`)
      .then(setSelected)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadPeriods();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitGenerate(e: React.FormEvent) {
    e.preventDefault();
    setGenerating(true);
    setGenerateError("");
    try {
      const period = await apiRequest<PayrollPeriodOut>("/api/v1/hr/payroll/generate", {
        method: "POST",
        body: {
          period_year: Number(generateForm.period_year),
          period_month: Number(generateForm.period_month),
          notes: generateForm.notes || null,
        },
      });
      setShowGenerateModal(false);
      setGenerateForm(EMPTY_GENERATE);
      loadPeriods(period.id);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Failed to generate payroll.");
    } finally {
      setGenerating(false);
    }
  }

  async function approveSelected() {
    if (!selected) return;
    if (!window.confirm("Approve this payroll period? Payslips will be finalized and can no longer be adjusted.")) return;
    setApproving(true);
    try {
      await apiRequest(`/api/v1/hr/payroll/${selected.id}/approve`, { method: "PATCH" });
      loadPeriods(selected.id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to approve payroll.");
    } finally {
      setApproving(false);
    }
  }

  function openEdit(slip: PayslipOut) {
    setEditTarget(slip);
    setAdjustForm({
      overtime_pay: String(slip.overtime_pay),
      bonus: String(slip.bonus),
      other_deductions: String(slip.other_deductions),
    });
    setAdjustError("");
  }

  async function submitAdjust(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget) return;
    setAdjustSaving(true);
    setAdjustError("");
    try {
      await apiRequest(`/api/v1/hr/payroll/payslips/${editTarget.id}`, {
        method: "PATCH",
        body: {
          overtime_pay: Number(adjustForm.overtime_pay),
          bonus: Number(adjustForm.bonus),
          other_deductions: Number(adjustForm.other_deductions),
        },
      });
      setEditTarget(null);
      if (selected) loadPeriods(selected.id); // refreshes both the sidebar totals and the detail view
    } catch (err) {
      setAdjustError(err instanceof Error ? err.message : "Failed to adjust payslip.");
    } finally {
      setAdjustSaving(false);
    }
  }

  function openPdf(id: string) {
    // The endpoint returns a print-ready HTML page with window.print() on load.
    window.open(`/api/v1/hr/payroll/payslips/${id}/pdf`, "_blank", "noopener");
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <FinanceSubNav />
      <PageHeader
        title="Payroll"
        subtitle="Monthly payroll periods"
        action={
          <button
            type="button"
            onClick={() => { setShowGenerateModal(true); setGenerateForm(EMPTY_GENERATE); setGenerateError(""); }}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors"
          >
            + Generate Payroll
          </button>
        }
      />

      <div className="flex gap-6">
        <div className="w-52 shrink-0 rounded-xl border border-white/6 bg-[#1e293b]">
          <div className="border-b border-white/6 px-4 py-3">
            <p className="text-xs font-semibold text-slate-400">Periods</p>
          </div>
          {periods.length === 0 ? (
            <p className="px-4 py-6 text-xs text-slate-500">No payroll generated yet.</p>
          ) : (
            <div className="divide-y divide-white/4">
              {periods.map((p) => (
                <button
                  type="button"
                  key={p.id}
                  onClick={() => loadPeriod(p.id)}
                  className={`w-full px-4 py-3 text-left transition-colors hover:bg-white/4 ${selected?.id === p.id ? "bg-white/6" : ""}`}
                >
                  <p className="text-sm font-medium text-white">
                    {MONTHS[p.period_month - 1]} {p.period_year}
                  </p>
                  <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${statusBadge(p.status)}`}>
                    {p.status}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1">
          {loading ? (
            <div className="text-sm text-slate-400">Loading…</div>
          ) : !selected ? (
            <div className="rounded-xl border border-white/6 bg-[#1e293b] p-8 text-center text-sm text-slate-500">
              Select a payroll period to view details, or generate one for the current month.
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-3 gap-4">
                {[
                  { label: "Total Gross",       value: fmt(selected.total_gross),       color: "bg-blue-500" },
                  { label: "Total Deductions",  value: fmt(selected.total_deductions),  color: "bg-rose-500" },
                  { label: "Total Net Pay",     value: fmt(selected.total_net),         color: "bg-emerald-500" },
                ].map((c) => (
                  <div key={c.label} className="erp-panel p-4">
                    <span className={`status-dot ${c.color} ${c.color.replace("bg-", "text-")}`} />
                    <p className="text-xs text-slate-400">{c.label}</p>
                    <p className="mt-1 text-xl font-bold text-white">{c.value}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-white/6 bg-[#1e293b]">
                <div className="flex items-center justify-between border-b border-white/6 px-5 py-3">
                  <p className="text-sm font-semibold text-slate-300">
                    Payslips — {selected.payslips.length} employees
                  </p>
                  {selected.status === "draft" && (
                    <button
                      type="button"
                      onClick={approveSelected}
                      disabled={approving}
                      className="erp-button-primary px-4 py-1.5 text-xs font-medium disabled:opacity-50 transition-colors"
                    >
                      {approving ? "Approving…" : "Approve Payroll"}
                    </button>
                  )}
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/4 text-left text-xs text-slate-500">
                      <th className="px-5 py-2.5 font-medium">Employee</th>
                      <th className="px-3 py-2.5 text-right font-medium">Gross</th>
                      <th className="px-3 py-2.5 text-right font-medium">PAYE</th>
                      <th className="px-3 py-2.5 text-right font-medium">UIF</th>
                      <th className="px-3 py-2.5 text-right font-medium">Net Pay</th>
                      <th className="px-5 py-2.5 font-medium">Status</th>
                      <th className="px-5 py-2.5 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/4">
                    {selected.payslips.map((slip) => (
                      <tr key={slip.id} className="hover:bg-white/2">
                        <td className="px-5 py-3 font-medium text-white">{slip.employee_name}</td>
                        <td className="px-3 py-3 text-right text-slate-400">{fmt(Number(slip.gross_pay))}</td>
                        <td className="px-3 py-3 text-right text-rose-400">{fmt(Number(slip.tax_deduction))}</td>
                        <td className="px-3 py-3 text-right text-rose-400">{fmt(Number(slip.uif_deduction))}</td>
                        <td className="px-3 py-3 text-right font-medium text-emerald-400">{fmt(Number(slip.net_pay))}</td>
                        <td className="px-5 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusBadge(slip.status)}`}>
                            {slip.status}
                          </span>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex gap-3 text-xs">
                            {selected.status === "draft" && (
                              <button type="button" onClick={() => openEdit(slip)} className="text-slate-400 hover:text-white transition-colors">
                                Adjust
                              </button>
                            )}
                            <button type="button" onClick={() => openPdf(slip.id)} className="text-slate-400 hover:text-white transition-colors">
                              PDF
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Generate Payroll Modal ── */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">Generate Payroll</h2>
              <button type="button" aria-label="Close" onClick={() => setShowGenerateModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitGenerate}>
              <div className="space-y-4 px-6 py-5">
                {generateError && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{generateError}</p>}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Year">
                    <input
                      type="number"
                      required
                      value={generateForm.period_year}
                      onChange={(e) => setGenerateForm((f) => ({ ...f, period_year: e.target.value }))}
                      className={INPUT}
                    />
                  </Field>
                  <Field label="Month">
                    <select
                      required
                      value={generateForm.period_month}
                      onChange={(e) => setGenerateForm((f) => ({ ...f, period_month: e.target.value }))}
                      className={`${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`}
                    >
                      {MONTHS.map((m, i) => (
                        <option key={m} value={i + 1}>{m}</option>
                      ))}
                    </select>
                  </Field>
                </div>
                <Field label="Notes (optional)">
                  <textarea
                    value={generateForm.notes}
                    onChange={(e) => setGenerateForm((f) => ({ ...f, notes: e.target.value }))}
                    className={INPUT}
                    rows={2}
                  />
                </Field>
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowGenerateModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={generating} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {generating ? "Generating…" : "Generate"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Adjust Payslip Modal ── */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">Adjust — {editTarget.employee_name}</h2>
              <button type="button" aria-label="Close" onClick={() => setEditTarget(null)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitAdjust}>
              <div className="space-y-4 px-6 py-5">
                {adjustError && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{adjustError}</p>}
                <Field label="Overtime pay">
                  <input
                    type="number" step="0.01"
                    value={adjustForm.overtime_pay}
                    onChange={(e) => setAdjustForm((f) => ({ ...f, overtime_pay: e.target.value }))}
                    className={INPUT}
                  />
                </Field>
                <Field label="Bonus">
                  <input
                    type="number" step="0.01"
                    value={adjustForm.bonus}
                    onChange={(e) => setAdjustForm((f) => ({ ...f, bonus: e.target.value }))}
                    className={INPUT}
                  />
                </Field>
                <Field label="Other deductions">
                  <input
                    type="number" step="0.01"
                    value={adjustForm.other_deductions}
                    onChange={(e) => setAdjustForm((f) => ({ ...f, other_deductions: e.target.value }))}
                    className={INPUT}
                  />
                </Field>
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setEditTarget(null)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={adjustSaving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {adjustSaving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
