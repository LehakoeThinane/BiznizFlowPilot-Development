"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest, downloadFile } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";

const PAGE_SIZE = 20;

interface Customer { id: string; name: string }
interface InvoiceListItem {
  id: string; invoice_number: string; customer_name: string | null;
  status: string; issue_date: string; due_date: string | null; total_amount: number;
}
interface InvoiceListResponse { items: InvoiceListItem[]; total: number }

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency: "ZAR", maximumFractionDigits: 0,
  }).format(n);
}

function statusColor(s: string) {
  if (s === "paid")      return "bg-emerald-500/20 text-emerald-300";
  if (s === "sent")      return "bg-blue-500/20 text-blue-300";
  if (s === "overdue")   return "bg-rose-500/20 text-rose-300";
  if (s === "draft")     return "bg-slate-500/30 text-slate-400";
  if (s === "cancelled") return "bg-orange-500/20 text-orange-300";
  return "bg-white/10 text-slate-300";
}

const STATUS_FILTERS = ["all", "draft", "sent", "paid", "overdue", "cancelled"];
const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;
const MINI = "erp-input w-full rounded-lg px-2 py-1.5 text-xs";

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

interface LineItem {
  description: string; quantity: string; unit_price: string;
  discount_percent: string; tax_rate: string;
}
const EMPTY_LINE: LineItem = { description: "", quantity: "1", unit_price: "", discount_percent: "0", tax_rate: "15" };

function calcLine(li: LineItem) {
  const qty  = Number(li.quantity)  || 0;
  const price = Number(li.unit_price) || 0;
  const disc  = Number(li.discount_percent) || 0;
  const tax   = Number(li.tax_rate) || 0;
  const sub   = qty * price;
  const afterDisc = sub * (1 - disc / 100);
  return afterDisc * (1 + tax / 100);
}

interface InvoiceForm {
  issue_date: string; due_date: string; customer_id: string; notes: string;
}
const EMPTY_FORM: InvoiceForm = { issue_date: "", due_date: "", customer_id: "", notes: "" };

export default function InvoicesPage() {
  const [items, setItems]   = useState<InvoiceListItem[]>([]);
  const [total, setTotal]   = useState(0);
  const [filter, setFilter] = useState("all");
  const [page, setPage]     = useState(1);
  const [loading, setLoading] = useState(true);

  const [customers, setCustomers] = useState<Customer[]>([]);

  const [showModal, setShowModal] = useState(false);
  const [form, setForm]           = useState<InvoiceForm>(EMPTY_FORM);
  const [lines, setLines]         = useState<LineItem[]>([{ ...EMPTY_LINE }]);
  const [formErrors, setFormErrors] = useState<Partial<InvoiceForm>>({});
  const [saving, setSaving]       = useState(false);
  const [serverError, setServerError] = useState("");

  // Status-change state
  const [statusTarget, setStatusTarget] = useState<{ id: string; current: string } | null>(null);
  const [newStatus, setNewStatus]       = useState("");
  const [statusSaving, setStatusSaving] = useState(false);

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<InvoiceListItem | null>(null);
  const [deleting, setDeleting]         = useState(false);
  const [deleteError, setDeleteError]   = useState<string | null>(null);

  // Status change error
  const [statusError, setStatusError]   = useState<string | null>(null);

  // Email feedback
  const [emailFeedback, setEmailFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [exporting, setExporting] = useState(false);

  const token = getStoredToken();

  const loadInvoices = useCallback(() => {
    setLoading(true);
    const skip = (page - 1) * PAGE_SIZE;
    const qs = filter !== "all" ? `&status=${filter}` : "";
    apiRequest<InvoiceListResponse>(`/api/v1/invoices?skip=${skip}&limit=${PAGE_SIZE}${qs}`, { authToken: token })
      .then((d) => { setItems(d.items ?? []); setTotal(d.total ?? 0); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter, token, page]);

  useEffect(() => { loadInvoices(); }, [loadInvoices]);

  useEffect(() => {
    apiRequest<{ items: Customer[]; total: number }>("/api/v1/customers?limit=100", { authToken: token })
      .then((d) => setCustomers(d.items ?? [])).catch(() => null);
  }, [token]);

  function setF(field: keyof InvoiceForm, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
    setFormErrors((e) => ({ ...e, [field]: undefined }));
  }

  function setLine(i: number, field: keyof LineItem, value: string) {
    setLines((prev) => prev.map((li, idx) => idx === i ? { ...li, [field]: value } : li));
  }

  function addLine() { setLines((prev) => [...prev, { ...EMPTY_LINE }]); }
  function removeLine(i: number) { setLines((prev) => prev.filter((_, idx) => idx !== i)); }

  const previewTotal = lines.reduce((s, li) => s + calcLine(li), 0);

  function validate(): boolean {
    const e: Partial<InvoiceForm> = {};
    if (!form.issue_date) e.issue_date = "Required";
    setFormErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true); setServerError("");
    try {
      const body: Record<string, unknown> = {
        issue_date: form.issue_date,
        line_items: lines.map((li) => ({
          description:      li.description || "Item",
          quantity:         li.quantity,
          unit_price:       li.unit_price || "0",
          discount_percent: li.discount_percent,
          tax_rate:         li.tax_rate,
        })),
      };
      if (form.due_date)    body.due_date    = form.due_date;
      if (form.customer_id) body.customer_id = form.customer_id;
      if (form.notes)       body.notes       = form.notes.trim();
      await apiRequest("/api/v1/invoices", { method: "POST", body, authToken: token });
      setShowModal(false); setForm(EMPTY_FORM); setLines([{ ...EMPTY_LINE }]);
      loadInvoices();
    } catch (err: unknown) {
      setServerError(err instanceof Error ? err.message : "Failed to create invoice.");
    } finally { setSaving(false); }
  }

  async function applyStatus() {
    if (!statusTarget || !newStatus) return;
    setStatusSaving(true);
    setStatusError(null);
    try {
      await apiRequest(`/api/v1/invoices/${statusTarget.id}/status`, {
        method: "PATCH", body: { status: newStatus }, authToken: token,
      });
      setStatusTarget(null);
      loadInvoices();
    } catch (err: unknown) {
      setStatusError(err instanceof Error ? err.message : "Failed to update status.");
    } finally { setStatusSaving(false); }
  }

  function openPdf(id: string) {
    // The endpoint returns a print-ready HTML page with window.print() on load.
    // Open it in a new tab — browser prints it directly (Save as PDF works too).
    window.open(`/api/v1/invoices/${id}/pdf`, "_blank", "noopener");
  }

  const [emailTarget, setEmailTarget] = useState<InvoiceListItem | null>(null);
  const [emailSending, setEmailSending] = useState(false);

  async function sendEmail(inv: InvoiceListItem) {
    setEmailTarget(inv);
    setEmailSending(true);
    setEmailFeedback(null);
    try {
      await apiRequest(`/api/v1/invoices/${inv.id}/send-email`, { method: "POST", authToken: token });
      setEmailFeedback({ type: "success", message: `Invoice ${inv.invoice_number} sent to customer.` });
    } catch (err: unknown) {
      setEmailFeedback({ type: "error", message: err instanceof Error ? err.message : "Failed to send email." });
    } finally {
      setEmailSending(false);
      setEmailTarget(null);
    }
  }

  async function confirmDeleteInvoice() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await apiRequest(`/api/v1/invoices/${deleteTarget.id}`, { method: "DELETE", authToken: token });
      setDeleteTarget(null);
      loadInvoices();
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete invoice.");
    } finally { setDeleting(false); }
  }

  const totalValue  = items.reduce((s, i) => s + Number(i.total_amount), 0);
  const outstanding = items
    .filter((i) => i.status === "sent" || i.status === "overdue")
    .reduce((s, i) => s + Number(i.total_amount), 0);

  async function handleExport() {
    setExporting(true);
    try {
      const q: Record<string, string> = {};
      if (filter !== "all") q.status = filter;
      await downloadFile("/api/v1/invoices/export", "invoices.csv", q);
    } catch (err: unknown) {
      console.error("Export failed", err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Invoices" subtitle={`${total} invoices`} />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="rounded-lg border border-white/10 px-3 py-2 text-sm text-slate-400 hover:text-white disabled:opacity-50 transition-colors"
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
          <button
            type="button"
            onClick={() => { setShowModal(true); setForm(EMPTY_FORM); setLines([{ ...EMPTY_LINE }]); setFormErrors({}); setServerError(""); }}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors"
          >
            + New Invoice
          </button>
        </div>
      </div>

      {/* ── KPI cards ── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Value",  value: fmt(totalValue),  color: "bg-blue-500" },
          { label: "Outstanding",  value: fmt(outstanding), color: "bg-orange-500" },
          { label: "Count",        value: String(total),    color: "bg-violet-500" },
        ].map((c) => (
          <div key={c.label} className="relative overflow-hidden erp-panel p-5">
            <div className={`absolute left-0 top-0 h-full w-1 ${c.color}`} />
            <p className="text-xs font-medium text-slate-400">{c.label}</p>
            <p className="mt-1.5 text-2xl font-bold text-white">{c.value}</p>
          </div>
        ))}
      </div>

      {/* ── Email feedback banner ── */}
      {emailFeedback && (
        <div className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
          emailFeedback.type === "success"
            ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-400"
            : "border-rose-900/40 bg-rose-950/30 text-rose-400"
        }`}>
          <span>{emailFeedback.message}</span>
          <button type="button" onClick={() => setEmailFeedback(null)} className="ml-4 text-xs opacity-70 hover:opacity-100">✕</button>
        </div>
      )}

      {/* ── Status filter tabs ── */}
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

      {/* ── Invoice list ── */}
      <div className="erp-panel">
        {loading ? (
          <div className="px-5 py-8 text-sm text-slate-400">Loading…</div>
        ) : items.length === 0 ? (
          <div className="px-5 py-8 text-sm text-slate-400">No invoices found.</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="min-w-175 w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant/80 text-left text-xs text-slate-500">
                <th className="px-5 py-3 font-medium">Invoice #</th>
                <th className="px-3 py-3 font-medium">Customer</th>
                <th className="px-3 py-3 font-medium">Status</th>
                <th className="px-3 py-3 font-medium">Issue Date</th>
                <th className="px-3 py-3 font-medium">Due Date</th>
                <th className="px-5 py-3 text-right font-medium">Amount</th>
                <th className="px-3 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/60">
              {items.map((inv) => (
                <tr key={inv.id} className="hover:bg-surface-container-high/70">
                  <td className="px-5 py-3 font-mono text-xs text-slate-300">{inv.invoice_number}</td>
                  <td className="px-3 py-3 text-white">{inv.customer_name ?? "—"}</td>
                  <td className="px-3 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusColor(inv.status)}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-slate-400">{inv.issue_date}</td>
                  <td className="px-3 py-3 text-slate-400">{inv.due_date ?? "—"}</td>
                  <td className="px-5 py-3 text-right font-medium text-white">{fmt(Number(inv.total_amount))}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => openPdf(inv.id)}
                        className="text-xs text-primary-fixed-dim hover:text-on-primary-container transition-colors"
                      >
                        PDF
                      </button>
                      {inv.status !== "draft" && inv.status !== "cancelled" && (
                        <button
                          type="button"
                          onClick={() => sendEmail(inv)}
                          disabled={emailSending && emailTarget?.id === inv.id}
                          className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors disabled:opacity-50"
                        >
                          {emailSending && emailTarget?.id === inv.id ? "Sending…" : "Email"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => { setStatusTarget({ id: inv.id, current: inv.status }); setNewStatus(inv.status); }}
                        className="text-xs text-slate-400 hover:text-white transition-colors"
                      >
                        Status
                      </button>
                      {inv.status === "draft" && (
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(inv)}
                          className="text-xs text-muted hover:text-rose-400 transition-colors"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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

      {/* ── New Invoice Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">New Invoice</h2>
              <button type="button" aria-label="Close" onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={handleSubmit} noValidate>
              <div className="max-h-[75vh] overflow-y-auto px-6 py-5 space-y-5">
                {/* Header fields */}
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Issue Date *" error={formErrors.issue_date}>
                    <input type="date" aria-label="Issue date" className={INPUT} value={form.issue_date} onChange={(e) => setF("issue_date", e.target.value)} />
                  </Field>
                  <Field label="Due Date">
                    <input type="date" aria-label="Due date" className={INPUT} value={form.due_date} onChange={(e) => setF("due_date", e.target.value)} />
                  </Field>
                  <Field label="Customer">
                    <select aria-label="Customer" className={SELECT} value={form.customer_id} onChange={(e) => setF("customer_id", e.target.value)}>
                      <option value="">No customer</option>
                      {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Notes">
                    <input className={INPUT} value={form.notes} onChange={(e) => setF("notes", e.target.value)} placeholder="Optional notes" />
                  </Field>
                </div>

                {/* Line items */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold text-slate-400">LINE ITEMS</p>
                    <button
                      type="button"
                      onClick={addLine}
                      className="text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      + Add row
                    </button>
                  </div>
                  <div className="overflow-x-auto rounded-lg border border-white/8">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-outline-variant text-left text-slate-500">
                          <th className="px-2 py-2 font-medium w-[30%]">Description</th>
                          <th className="px-2 py-2 font-medium w-[10%]">Qty</th>
                          <th className="px-2 py-2 font-medium w-[15%]">Unit Price</th>
                          <th className="px-2 py-2 font-medium w-[12%]">Disc %</th>
                          <th className="px-2 py-2 font-medium w-[12%]">VAT %</th>
                          <th className="px-2 py-2 text-right font-medium w-[15%]">Total</th>
                          <th className="px-2 py-2 font-medium w-[6%]">Remove</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-outline-variant/60">
                        {lines.map((li, i) => (
                          <tr key={i}>
                            <td className="px-2 py-1.5">
                              <input
                                aria-label={`Line ${i + 1} description`}
                                className={MINI}
                                value={li.description}
                                onChange={(e) => setLine(i, "description", e.target.value)}
                                placeholder="Item description"
                              />
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                aria-label={`Line ${i + 1} quantity`}
                                type="number" min="0" step="1" className={MINI}
                                value={li.quantity}
                                onChange={(e) => setLine(i, "quantity", e.target.value)}
                              />
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                aria-label={`Line ${i + 1} unit price`}
                                type="number" min="0" step="0.01" className={MINI}
                                value={li.unit_price}
                                onChange={(e) => setLine(i, "unit_price", e.target.value)}
                                placeholder="0.00"
                              />
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                aria-label={`Line ${i + 1} discount percent`}
                                type="number" min="0" max="100" step="1" className={MINI}
                                value={li.discount_percent}
                                onChange={(e) => setLine(i, "discount_percent", e.target.value)}
                              />
                            </td>
                            <td className="px-2 py-1.5">
                              <input
                                aria-label={`Line ${i + 1} tax rate`}
                                type="number" min="0" max="100" step="1" className={MINI}
                                value={li.tax_rate}
                                onChange={(e) => setLine(i, "tax_rate", e.target.value)}
                              />
                            </td>
                            <td className="px-2 py-1.5 text-right font-medium text-white">
                              {fmt(calcLine(li))}
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              {lines.length > 1 && (
                                <button
                                  type="button"
                                  aria-label={`Remove line ${i + 1}`}
                                  onClick={() => removeLine(i)}
                                  className="text-slate-500 hover:text-rose-400 transition-colors"
                                >
                                  ×
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <div className="w-64 space-y-1 text-sm">
                      {(() => {
                        const exVat = lines.reduce((s, li) => {
                          const qty = Number(li.quantity) || 0;
                          const price = Number(li.unit_price) || 0;
                          const disc = Number(li.discount_percent) || 0;
                          return s + qty * price * (1 - disc / 100);
                        }, 0);
                        const vat = previewTotal - exVat;
                        return (
                          <>
                            <div className="flex justify-between text-slate-400">
                              <span>Subtotal (excl. VAT)</span>
                              <span>{fmt(exVat)}</span>
                            </div>
                            <div className="flex justify-between text-slate-400">
                              <span>VAT (15%)</span>
                              <span>{fmt(vat)}</span>
                            </div>
                            <div className="flex justify-between border-t border-outline-variant pt-1 font-semibold text-white">
                              <span>Total (incl. VAT)</span>
                              <span className="text-blue-300">{fmt(previewTotal)}</span>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                </div>

                {serverError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{serverError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={saving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {saving ? "Creating…" : "Create Invoice"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Change Status Modal ── */}
      {statusTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-xs overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">Change Status</h2>
              <button type="button" aria-label="Close" onClick={() => setStatusTarget(null)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <div className="px-6 py-5 space-y-3">
              <select
                aria-label="New invoice status"
                className={SELECT}
                value={newStatus}
                onChange={(e) => { setNewStatus(e.target.value); setStatusError(null); }}
              >
                {["draft", "sent", "paid", "overdue", "cancelled"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              {statusError && (
                <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{statusError}</p>
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
              <button type="button" onClick={() => { setStatusTarget(null); setStatusError(null); }} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
              <button
                type="button"
                disabled={statusSaving}
                onClick={applyStatus}
                className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {statusSaving ? "Saving…" : "Apply"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Invoice Confirmation ─────────────────────────────────── */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-surface shadow-2xl">
            <div className="px-6 py-5">
              <p className="text-base font-semibold text-on-surface">Delete invoice?</p>
              <p className="mt-1 text-sm text-on-surface-variant">
                Invoice <strong className="text-on-surface">{deleteTarget.invoice_number}</strong> will be permanently removed. This cannot be undone.
              </p>
              {deleteError && (
                <p className="mt-3 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{deleteError}</p>
              )}
            </div>
            <div className="flex justify-end gap-3 border-t border-outline-variant px-6 py-4">
              <button type="button" onClick={() => { setDeleteTarget(null); setDeleteError(null); }} className="rounded-lg px-4 py-2 text-sm text-on-surface-variant hover:text-on-surface transition-colors">
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={confirmDeleteInvoice}
                className="rounded-lg bg-rose-600 px-5 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50 transition-colors"
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

