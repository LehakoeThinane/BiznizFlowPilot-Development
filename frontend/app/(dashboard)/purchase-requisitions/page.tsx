"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import type {
  PurchaseRequisition,
  PurchaseRequisitionListResponse,
  PurchaseRequisitionStatus,
  PRLineItem,
  PurchaseOrder,
  Supplier,
  SupplierListResponse,
} from "@/types/api";

const STATUS_COLORS: Record<PurchaseRequisitionStatus, string> = {
  pending: "bg-yellow-500/20 text-yellow-300",
  approved: "bg-emerald-500/20 text-emerald-300",
  rejected: "bg-rose-500/20 text-rose-300",
  cancelled: "bg-white/10 text-[#aaa]",
  converted: "bg-blue-500/20 text-blue-300",
};

const STATUS_OPTIONS: PurchaseRequisitionStatus[] = [
  "pending",
  "approved",
  "rejected",
  "cancelled",
  "converted",
];

function StatusBadge({ status }: { status: PurchaseRequisitionStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[status]}`}
    >
      {status}
    </span>
  );
}

function DetailItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-[#888] uppercase tracking-wide">{label}</dt>
      <dd className="mt-1 text-sm text-white">{value ?? "—"}</dd>
    </div>
  );
}

function fmt(amount: string | null | undefined): string {
  if (!amount) return "—";
  return `$${parseFloat(amount).toFixed(2)}`;
}

type DraftLineItem = { description: string; quantity: string; estimated_unit_cost: string };

export default function PurchaseRequisitionsPage() {
  const [requisitions, setRequisitions] = useState<PurchaseRequisition[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [activeFilter, setActiveFilter] = useState<"all" | PurchaseRequisitionStatus>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [selected, setSelected] = useState<PurchaseRequisition | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [isActing, setIsActing] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    justification: "",
    supplier_id: "",
    estimated_total: "",
  });
  const [draftItems, setDraftItems] = useState<DraftLineItem[]>([]);

  const PAGE_SIZE = 20;

  useEffect(() => {
    loadData();
  }, [page]);

  async function loadData() {
    setIsLoading(true);
    setError(null);
    try {
      const [reqRes, suppRes] = await Promise.all([
        apiRequest<PurchaseRequisitionListResponse>(
          `/api/v1/purchase-requisitions?skip=${(page - 1) * PAGE_SIZE}&limit=${PAGE_SIZE}`
        ),
        apiRequest<SupplierListResponse>(`/api/v1/suppliers?skip=0&limit=200`),
      ]);
      setRequisitions(reqRes.items);
      setTotal(reqRes.total);
      setSuppliers(suppRes.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load purchase requisitions");
    } finally {
      setIsLoading(false);
    }
  }

  function supplierName(id: string | null): string {
    if (!id) return "—";
    const s = suppliers.find((s) => s.id === id);
    return s ? s.name : id.slice(0, 8) + "…";
  }

  const visible = useMemo(() => {
    if (activeFilter === "all") return requisitions;
    return requisitions.filter((r) => r.status === activeFilter);
  }, [requisitions, activeFilter]);

  function openRequisition(req: PurchaseRequisition) {
    setSelected(req);
    setRejectionReason("");
  }

  function closePanel() {
    setSelected(null);
    setRejectionReason("");
  }

  function flash(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 4000);
  }

  async function handleDecision(status: "approved" | "rejected" | "cancelled") {
    if (!selected) return;
    setIsActing(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { status };
      if (status === "rejected") body.rejection_reason = rejectionReason || null;
      const updated = await apiRequest<PurchaseRequisition>(
        `/api/v1/purchase-requisitions/${selected.id}/status`,
        { method: "PATCH", body }
      );
      setRequisitions((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setSelected(updated);
      flash(`Requisition ${status}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to mark requisition as ${status}`);
    } finally {
      setIsActing(false);
    }
  }

  async function handleConvert() {
    if (!selected) return;
    setIsActing(true);
    setError(null);
    try {
      const po = await apiRequest<PurchaseOrder>(
        `/api/v1/purchase-requisitions/${selected.id}/convert`,
        { method: "POST" }
      );
      const updated = await apiRequest<PurchaseRequisition>(
        `/api/v1/purchase-requisitions/${selected.id}`
      );
      setRequisitions((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setSelected(updated);
      flash(`Converted to purchase order ${po.po_number}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to convert to a purchase order");
    } finally {
      setIsActing(false);
    }
  }

  function addDraftItem() {
    setDraftItems((items) => [...items, { description: "", quantity: "1", estimated_unit_cost: "" }]);
  }

  function updateDraftItem(index: number, field: keyof DraftLineItem, value: string) {
    setDraftItems((items) =>
      items.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  }

  function removeDraftItem(index: number) {
    setDraftItems((items) => items.filter((_, i) => i !== index));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingCreate(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        title: createForm.title,
        estimated_total: createForm.estimated_total || "0",
      };
      if (createForm.justification) body.justification = createForm.justification;
      if (createForm.supplier_id) body.supplier_id = createForm.supplier_id;
      body.line_items = draftItems
        .filter((item) => item.description.trim())
        .map((item) => ({
          description: item.description,
          quantity: parseInt(item.quantity, 10) || 1,
          estimated_unit_cost: item.estimated_unit_cost || null,
        }));

      const created = await apiRequest<PurchaseRequisition>("/api/v1/purchase-requisitions", {
        method: "POST",
        body,
      });
      setRequisitions((prev) => [created, ...prev]);
      setTotal((t) => t + 1);
      setIsCreateOpen(false);
      setCreateForm({ title: "", justification: "", supplier_id: "", estimated_total: "" });
      setDraftItems([]);
      flash("Purchase requisition submitted");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit requisition");
    } finally {
      setIsSavingCreate(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Purchase Requisitions</h1>
          <p className="mt-1 text-sm text-[#888]">
            {total} requisition{total !== 1 ? "s" : ""} total — request a purchase, get it approved, then convert it to a PO.
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90"
        >
          + Request Purchase
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 p-3 text-sm text-red-400">{error}</div>
      )}
      {successMessage && (
        <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 p-3 text-sm text-emerald-400">{successMessage}</div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-1">
        {(["all", ...STATUS_OPTIONS] as const).map((s) => (
          <button
            key={s}
            onClick={() => setActiveFilter(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
              activeFilter === s
                ? "bg-brand text-white"
                : "bg-white/10 text-[#aaa] hover:bg-white/[0.08]"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-[#222] bg-[#141414] shadow-sm">
        <table className="min-w-full divide-y divide-[#222]">
          <thead className="bg-[#1a1a1a]">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Title</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Supplier</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Estimated Total</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Items</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">Submitted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#222]">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#888]">Loading…</td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#888]">No purchase requisitions found.</td>
              </tr>
            ) : (
              visible.map((req) => (
                <tr
                  key={req.id}
                  className="cursor-pointer hover:bg-white/[0.02] transition-colors"
                  onClick={() => openRequisition(req)}
                >
                  <td className="px-4 py-3 text-sm font-medium text-white">{req.title}</td>
                  <td className="px-4 py-3 text-sm text-[#aaa]">{supplierName(req.supplier_id)}</td>
                  <td className="px-4 py-3"><StatusBadge status={req.status} /></td>
                  <td className="px-4 py-3 text-sm text-[#aaa] font-medium">{fmt(req.estimated_total)}</td>
                  <td className="px-4 py-3 text-sm text-[#888]">{req.line_items?.length ?? 0}</td>
                  <td className="px-4 py-3 text-sm text-[#888]">{new Date(req.created_at).toLocaleDateString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-[#888]">
          <span>Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-[#333] px-3 py-1 disabled:opacity-40 hover:bg-white/[0.02]"
            >
              Prev
            </button>
            <button
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-[#333] px-3 py-1 disabled:opacity-40 hover:bg-white/[0.02]"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Create Panel */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={() => setIsCreateOpen(false)} />
          <div className="w-full max-w-md bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Request a Purchase</h2>
              <button onClick={() => setIsCreateOpen(false)} className="text-[#666] hover:text-[#aaa] text-xl leading-none">×</button>
            </div>
            <form onSubmit={handleCreate} className="flex-1 space-y-5 px-6 py-5">
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">What do you need? *</label>
                <input
                  required
                  type="text"
                  value={createForm.title}
                  onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Replacement laptop for design team"
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Why do you need it?</label>
                <textarea
                  value={createForm.justification}
                  onChange={(e) => setCreateForm((f) => ({ ...f, justification: e.target.value }))}
                  rows={3}
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Preferred Supplier</label>
                <select
                  value={createForm.supplier_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, supplier_id: e.target.value }))}
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                >
                  <option value="">— Not sure yet —</option>
                  {suppliers.filter((s) => s.is_active).map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Estimated Total *</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={createForm.estimated_total}
                  onChange={(e) => setCreateForm((f) => ({ ...f, estimated_total: e.target.value }))}
                  placeholder="0.00"
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-medium text-[#aaa]">Items (optional)</label>
                  <button type="button" onClick={addDraftItem} className="text-xs text-brand hover:underline">+ Add item</button>
                </div>
                <div className="space-y-2">
                  {draftItems.map((item, i) => (
                    <div key={i} className="flex gap-2 items-start">
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => updateDraftItem(i, "description", e.target.value)}
                        placeholder="Description"
                        className="flex-1 rounded-md border border-[#333] px-2 py-1.5 text-xs bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                      />
                      <input
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => updateDraftItem(i, "quantity", e.target.value)}
                        placeholder="Qty"
                        className="w-16 rounded-md border border-[#333] px-2 py-1.5 text-xs bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                      />
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={item.estimated_unit_cost}
                        onChange={(e) => updateDraftItem(i, "estimated_unit_cost", e.target.value)}
                        placeholder="Unit cost"
                        className="w-20 rounded-md border border-[#333] px-2 py-1.5 text-xs bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                      />
                      <button
                        type="button"
                        onClick={() => removeDraftItem(i)}
                        className="text-[#666] hover:text-rose-400 text-sm leading-none px-1"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={isSavingCreate}
                  className="flex-1 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:opacity-60"
                >
                  {isSavingCreate ? "Submitting…" : "Submit Request"}
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="rounded-md border border-[#333] px-4 py-2 text-sm text-[#aaa] hover:bg-white/[0.02]"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail Panel */}
      {selected && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={closePanel} />
          <div className="w-full max-w-xl bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-white">{selected.title}</h2>
                <StatusBadge status={selected.status} />
              </div>
              <button onClick={closePanel} className="text-[#666] hover:text-[#aaa] text-xl leading-none">×</button>
            </div>

            <div className="flex-1 space-y-6 px-6 py-5">
              <dl className="grid grid-cols-2 gap-4">
                <DetailItem label="Supplier" value={supplierName(selected.supplier_id)} />
                <DetailItem label="Estimated Total" value={fmt(selected.estimated_total)} />
                <DetailItem label="Submitted" value={new Date(selected.created_at).toLocaleString()} />
                <DetailItem
                  label="Decided"
                  value={selected.approved_at ? new Date(selected.approved_at).toLocaleString() : "—"}
                />
              </dl>

              {selected.justification && (
                <div>
                  <dt className="text-xs font-medium text-[#888] uppercase tracking-wide">Justification</dt>
                  <dd className="mt-1 text-sm text-[#aaa] whitespace-pre-wrap">{selected.justification}</dd>
                </div>
              )}

              {selected.rejection_reason && (
                <div>
                  <dt className="text-xs font-medium text-[#888] uppercase tracking-wide">Rejection Reason</dt>
                  <dd className="mt-1 text-sm text-rose-300 whitespace-pre-wrap">{selected.rejection_reason}</dd>
                </div>
              )}

              <div>
                <h3 className="text-sm font-medium text-white mb-3">
                  Items ({selected.line_items?.length ?? 0})
                </h3>
                {!selected.line_items || selected.line_items.length === 0 ? (
                  <p className="text-sm text-[#666] italic">No items listed.</p>
                ) : (
                  <div className="overflow-hidden rounded-lg border border-[#222]">
                    <table className="min-w-full divide-y divide-[#222] text-sm">
                      <thead className="bg-[#1a1a1a]">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-[#888] uppercase">Description</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">Qty</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">Est. Unit Cost</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#222]">
                        {selected.line_items.map((item: PRLineItem) => (
                          <tr key={item.id}>
                            <td className="px-3 py-2 text-[#aaa]">{item.description}</td>
                            <td className="px-3 py-2 text-right text-[#aaa]">{item.quantity}</td>
                            <td className="px-3 py-2 text-right text-[#aaa]">{fmt(item.estimated_unit_cost)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {selected.status === "pending" && (
                <div className="border-t border-[#222] pt-5 space-y-3">
                  <h3 className="text-sm font-medium text-white">Decide</h3>
                  <textarea
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    placeholder="Rejection reason (only needed if rejecting)"
                    rows={2}
                    className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                  />
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleDecision("approved")}
                      disabled={isActing}
                      className="flex-1 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleDecision("rejected")}
                      disabled={isActing}
                      className="flex-1 rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-60"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleDecision("cancelled")}
                      disabled={isActing}
                      className="rounded-md border border-[#333] px-4 py-2 text-sm text-[#aaa] hover:bg-white/[0.02] disabled:opacity-60"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {selected.status === "approved" && (
                <div className="border-t border-[#222] pt-5">
                  <h3 className="text-sm font-medium text-white mb-3">Ready to buy</h3>
                  <button
                    onClick={handleConvert}
                    disabled={isActing}
                    className="w-full rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:opacity-60"
                  >
                    {isActing ? "Converting…" : "Convert to Purchase Order"}
                  </button>
                </div>
              )}

              {selected.status === "converted" && selected.converted_purchase_order_id && (
                <div className="border-t border-[#222] pt-5 text-sm text-[#888]">
                  Converted to purchase order. View it under{" "}
                  <a href="/purchase-orders" className="text-brand hover:underline">Purchase Orders</a>.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
