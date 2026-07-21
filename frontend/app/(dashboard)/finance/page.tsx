"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest, downloadFile } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { FinanceSubNav } from "@/components/FinanceSubNav";

const PAGE_SIZE = 20;

interface CategoryTotal { name: string; amount: number }
interface FinanceSummary {
  period_label: string; revenue: number; expenses: number;
  net_profit: number; expense_by_category: CategoryTotal[];
}
interface Category { id: string; name: string }
interface Expense {
  id: string; date: string; amount: number; description: string;
  vendor: string | null; category_id: string | null; category_name: string | null;
}
interface ExpenseListResponse { items: Expense[]; total: number }

const PERIODS = [
  { value: "this_month", label: "This Month" },
  { value: "last_month", label: "Last Month" },
  { value: "ytd",        label: "Year to Date" },
  { value: "this_year",  label: "Full Year" },
];

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency: "ZAR", maximumFractionDigits: 0,
  }).format(n);
}

function KpiCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div className="erp-panel p-5">
      <span className={`status-dot ${color} ${color.replace("bg-", "text-")}`} />
      <p className="text-xs font-medium text-slate-400">{label}</p>
      <p className="mt-1.5 text-2xl font-bold text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

const INPUT = "erp-input w-full px-3 py-2 text-sm [&>option]:bg-[#0f1c33] [&>option]:text-white";
const SELECT = `${INPUT} appearance-none`;

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

interface ExpenseForm {
  date: string; amount: string; description: string; vendor: string; category_id: string;
}
const EMPTY_EXPENSE: ExpenseForm = { date: "", amount: "", description: "", vendor: "", category_id: "" };
interface CategoryForm { name: string; description: string }
const EMPTY_CAT: CategoryForm = { name: "", description: "" };

export default function FinancePage() {
  const [period, setPeriod] = useState("this_month");
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const [expenses, setExpenses]   = useState<Expense[]>([]);
  const [expTotal, setExpTotal]   = useState(0);
  const [expPage, setExpPage]     = useState(1);
  const [expLoading, setExpLoading] = useState(true);
  const [categories, setCategories] = useState<Category[]>([]);

  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [expError, setExpError]         = useState<string | null>(null);

  const [showExpModal, setShowExpModal] = useState(false);
  const [editTarget, setEditTarget]     = useState<Expense | null>(null);
  const [expForm, setExpForm]           = useState<ExpenseForm>(EMPTY_EXPENSE);
  const [expErrors, setExpErrors]       = useState<Partial<ExpenseForm>>({});
  const [expSaving, setExpSaving]       = useState(false);
  const [expServerError, setExpServerError] = useState("");

  const [showCatModal, setShowCatModal] = useState(false);
  const [catForm, setCatForm]           = useState<CategoryForm>(EMPTY_CAT);
  const [catSaving, setCatSaving]       = useState(false);
  const [catServerError, setCatServerError] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<Expense | null>(null);
  const [deleting, setDeleting]         = useState(false);
  const [deleteError, setDeleteError]   = useState<string | null>(null);

  const [exporting, setExporting] = useState(false);

  const token = getStoredToken();

  const loadSummary = useCallback(() => {
    setSummaryLoading(true);
    setSummaryError(null);
    apiRequest<FinanceSummary>(`/api/v1/finance/summary?period=${period}`, { authToken: token })
      .then((d) => { setSummary(d); setSummaryError(null); })
      .catch((err) => setSummaryError(err instanceof Error ? err.message : "Failed to load summary"))
      .finally(() => setSummaryLoading(false));
  }, [period, token]);

  const loadExpenses = useCallback(() => {
    setExpLoading(true);
    setExpError(null);
    const skip = (expPage - 1) * PAGE_SIZE;
    apiRequest<ExpenseListResponse>(`/api/v1/finance/expenses?skip=${skip}&limit=${PAGE_SIZE}`, { authToken: token })
      .then((d) => { setExpenses(d.items ?? []); setExpTotal(d.total ?? 0); setExpError(null); })
      .catch((err) => setExpError(err instanceof Error ? err.message : "Failed to load expenses"))
      .finally(() => setExpLoading(false));
  }, [token, expPage]);

  const loadCategories = useCallback(() => {
    apiRequest<Category[]>("/api/v1/finance/categories", { authToken: token })
      .then(setCategories).catch(() => null);
  }, [token]);

  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { loadExpenses(); loadCategories(); }, [loadExpenses, loadCategories]);

  function setExp(field: keyof ExpenseForm, value: string) {
    setExpForm((f) => ({ ...f, [field]: value }));
    setExpErrors((e) => ({ ...e, [field]: undefined }));
  }

  function openAdd() {
    setEditTarget(null);
    setExpForm(EMPTY_EXPENSE);
    setExpErrors({});
    setExpServerError("");
    setShowExpModal(true);
  }

  function openEdit(exp: Expense) {
    setEditTarget(exp);
    setExpForm({
      date: exp.date,
      amount: String(exp.amount),
      description: exp.description,
      vendor: exp.vendor ?? "",
      category_id: exp.category_id ?? "",
    });
    setExpErrors({});
    setExpServerError("");
    setShowExpModal(true);
  }

  function validateExp(): boolean {
    const e: Partial<ExpenseForm> = {};
    if (!expForm.date) e.date = "Required";
    if (!expForm.amount || isNaN(Number(expForm.amount))) e.amount = "Must be a number";
    if (!expForm.description.trim()) e.description = "Required";
    setExpErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submitExpense(e: React.FormEvent) {
    e.preventDefault();
    if (!validateExp()) return;
    setExpSaving(true); setExpServerError("");
    try {
      const body: Record<string, unknown> = {
        date: expForm.date,
        amount: Number(expForm.amount),
        description: expForm.description.trim(),
        vendor: expForm.vendor.trim() || null,
        category_id: expForm.category_id || null,
      };
      if (editTarget) {
        await apiRequest(`/api/v1/finance/expenses/${editTarget.id}`, { method: "PATCH", body, authToken: token });
      } else {
        await apiRequest("/api/v1/finance/expenses", { method: "POST", body, authToken: token });
      }
      setShowExpModal(false); setExpForm(EMPTY_EXPENSE); setEditTarget(null);
      loadExpenses(); loadSummary();
    } catch (err: unknown) {
      setExpServerError(err instanceof Error ? err.message : "Failed to save expense.");
    } finally { setExpSaving(false); }
  }

  async function confirmDeleteExpense() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await apiRequest(`/api/v1/finance/expenses/${deleteTarget.id}`, { method: "DELETE", authToken: token });
      setDeleteTarget(null);
      loadExpenses(); loadSummary();
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete expense.");
    } finally { setDeleting(false); }
  }

  async function submitCategory(e: React.FormEvent) {
    e.preventDefault();
    if (!catForm.name.trim()) return;
    setCatSaving(true); setCatServerError("");
    try {
      const body: Record<string, unknown> = { name: catForm.name.trim() };
      if (catForm.description) body.description = catForm.description.trim();
      await apiRequest("/api/v1/finance/categories", { method: "POST", body, authToken: token });
      setShowCatModal(false); setCatForm(EMPTY_CAT);
      loadCategories();
    } catch (err: unknown) {
      setCatServerError(err instanceof Error ? err.message : "Failed to create category.");
    } finally { setCatSaving(false); }
  }

  const margin = summary && summary.revenue > 0
    ? ((summary.net_profit / summary.revenue) * 100).toFixed(1)
    : "0.0";

  async function handleExport() {
    setExporting(true);
    try {
      await downloadFile("/api/v1/finance/expenses/export", "expenses.csv");
    } catch (err: unknown) {
      console.error("Export failed", err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <FinanceSubNav />
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <PageHeader title="Finance" subtitle={summary?.period_label ?? ""} />
        <div className="flex items-center gap-2">
          <select
            aria-label="Select period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="erp-input rounded-lg px-3 py-2 text-sm [&>option]:bg-[#0f1c33] [&>option]:text-white"
          >
            {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <button type="button"
            onClick={() => { setShowCatModal(true); setCatForm(EMPTY_CAT); setCatServerError(""); }}
            className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-400 hover:text-white transition-colors">
            + Category
          </button>
          <button type="button" onClick={openAdd}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors">
            + Add Expense
          </button>
        </div>
      </div>

      {/* ── KPI cards ── */}
      {summaryError && (
        <div className="flex items-center justify-between rounded-lg border border-rose-900/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-400">
          <span>{summaryError}</span>
          <button type="button" onClick={loadSummary} className="ml-4 rounded border border-rose-800 px-2 py-0.5 text-xs hover:bg-rose-950 transition-colors">
            Retry
          </button>
        </div>
      )}

      {summaryLoading ? (
        <div className="text-sm text-slate-400">Loading…</div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiCard label="Revenue"    value={fmt(summary.revenue)}    color="bg-emerald-500" />
            <KpiCard label="Expenses"   value={fmt(summary.expenses)}   color="bg-rose-500" />
            <KpiCard label="Net Profit" value={fmt(summary.net_profit)}
              color={summary.net_profit >= 0 ? "bg-blue-500" : "bg-orange-500"} />
            <KpiCard label="Margin" value={`${margin}%`} sub="Net profit / Revenue" color="bg-violet-500" />
          </div>

          {summary.expense_by_category.length > 0 && (
            <div className="erp-panel p-5">
              <h2 className="mb-4 text-sm font-semibold text-slate-300">Expenses by Category</h2>
              <div className="divide-y divide-white/6">
                {[...summary.expense_by_category].sort((a, b) => b.amount - a.amount).map((cat) => {
                  const pct = summary.expenses > 0 ? (cat.amount / summary.expenses) * 100 : 0;
                  return (
                    <div key={cat.name} className="flex items-center justify-between py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-rose-500" />
                        <span className="text-sm text-slate-300">{cat.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-500">{pct.toFixed(1)}%</span>
                        <span className="text-sm font-medium text-white">{fmt(cat.amount)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      ) : !summaryError ? (
        <div className="text-sm text-slate-400">No data available for this period.</div>
      ) : null}

      {/* ── Expense list ── */}
      <div className="erp-panel">
        <div className="flex items-center justify-between border-b border-outline-variant/80 px-5 py-3">
          <p className="text-sm font-semibold text-slate-300">Recent Expenses</p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:text-white disabled:opacity-50 transition-colors"
            >
              {exporting ? "Exporting…" : "Export CSV"}
            </button>
            <span className="text-xs text-slate-500">{expTotal} total</span>
          </div>
        </div>
        {expError && (
          <div className="flex items-center justify-between border-b border-rose-900/40 bg-rose-950/30 px-5 py-3 text-sm text-rose-400">
            <span>{expError}</span>
            <button type="button" onClick={loadExpenses} className="ml-4 rounded border border-rose-800 px-2 py-0.5 text-xs hover:bg-rose-950 transition-colors">
              Retry
            </button>
          </div>
        )}
        {expLoading ? (
          <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
        ) : expError ? null : expenses.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">
            No expenses yet. Click <strong className="text-white">+ Add Expense</strong> to record one.
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="min-w-160 w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant/80 text-left text-xs text-slate-500">
                <th className="px-5 py-3 font-medium">Date</th>
                <th className="px-3 py-3 font-medium">Description</th>
                <th className="px-3 py-3 font-medium">Vendor</th>
                <th className="px-3 py-3 font-medium">Category</th>
                <th className="px-5 py-3 text-right font-medium">Amount</th>
                <th className="px-3 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/60">
              {expenses.map((exp) => (
                <tr key={exp.id} className="hover:bg-surface-container-high/70">
                  <td className="px-5 py-3 text-slate-400 whitespace-nowrap">{exp.date}</td>
                  <td className="px-3 py-3 text-white">{exp.description}</td>
                  <td className="px-3 py-3 text-slate-400">{exp.vendor ?? "—"}</td>
                  <td className="px-3 py-3 text-slate-400">{exp.category_name ?? "—"}</td>
                  <td className="px-5 py-3 text-right font-medium text-white">{fmt(Number(exp.amount))}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-3">
                      <button type="button" onClick={() => openEdit(exp)}
                        className="text-xs text-slate-400 hover:text-blue-400 transition-colors">
                        Edit
                      </button>
                      <button type="button" onClick={() => setDeleteTarget(exp)}
                        className="text-xs text-slate-500 hover:text-rose-400 transition-colors">
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
        <Pagination
          page={expPage}
          totalPages={Math.max(1, Math.ceil(expTotal / PAGE_SIZE))}
          totalItems={expTotal}
          pageSize={PAGE_SIZE}
          onPrev={() => setExpPage((p) => p - 1)}
          onNext={() => setExpPage((p) => p + 1)}
        />
      </div>

      {/* ── Add / Edit Expense Modal ── */}
      {showExpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">
                {editTarget ? "Edit Expense" : "Add Expense"}
              </h2>
              <button type="button" aria-label="Close" onClick={() => setShowExpModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitExpense} noValidate>
              <div className="space-y-4 px-6 py-5">
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Date *" error={expErrors.date}>
                    <input type="date" aria-label="Expense date" className={INPUT} value={expForm.date} onChange={(e) => setExp("date", e.target.value)} />
                  </Field>
                  <Field label="Amount (R) *" error={expErrors.amount}>
                    <input type="number" min="0" step="0.01" className={INPUT} value={expForm.amount} onChange={(e) => setExp("amount", e.target.value)} placeholder="1500.00" />
                  </Field>
                </div>
                <Field label="Description *" error={expErrors.description}>
                  <input className={INPUT} value={expForm.description} onChange={(e) => setExp("description", e.target.value)} placeholder="e.g. Office supplies" />
                </Field>
                <Field label="Vendor">
                  <input className={INPUT} value={expForm.vendor} onChange={(e) => setExp("vendor", e.target.value)} placeholder="e.g. Builders Warehouse" />
                </Field>
                <Field label="Category">
                  <select aria-label="Category" className={SELECT} value={expForm.category_id} onChange={(e) => setExp("category_id", e.target.value)}>
                    <option value="">No category</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </Field>
                {expServerError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{expServerError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowExpModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={expSaving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {expSaving ? "Saving…" : editTarget ? "Save changes" : "Add Expense"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Add Category Modal ── */}
      {showCatModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">Add Category</h2>
              <button type="button" aria-label="Close" onClick={() => setShowCatModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submitCategory} noValidate>
              <div className="space-y-4 px-6 py-5">
                <Field label="Name *">
                  <input className={INPUT} value={catForm.name}
                    onChange={(e) => setCatForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Travel" />
                </Field>
                <Field label="Description">
                  <input className={INPUT} value={catForm.description}
                    onChange={(e) => setCatForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" />
                </Field>
                {catServerError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{catServerError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowCatModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={catSaving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {catSaving ? "Saving…" : "Add Category"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Expense Confirmation ── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="px-6 py-5">
              <p className="text-base font-semibold text-white">Delete expense?</p>
              <p className="mt-1 text-sm text-slate-400">
                <strong className="text-white">{deleteTarget.description}</strong> — {fmt(Number(deleteTarget.amount))}. This cannot be undone.
              </p>
              {deleteError && (
                <p className="mt-3 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{deleteError}</p>
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-white/10 px-6 py-4">
              <button type="button" onClick={() => { setDeleteTarget(null); setDeleteError(null); }} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
              <button type="button" disabled={deleting} onClick={confirmDeleteExpense}
                className="rounded-lg bg-rose-600 px-5 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50 transition-colors">
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

