"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import type {
  PurchaseOrder,
  PurchaseOrderListResponse,
  PurchaseOrderStatus,
  POLineItem,
  Supplier,
  SupplierListResponse,
} from "@/types/api";

const STATUS_COLORS: Record<PurchaseOrderStatus, string> = {
  draft: "bg-white/10 text-[#aaa]",
  sent: "bg-blue-500/20 text-blue-300",
  confirmed: "bg-indigo-500/20 text-indigo-300",
  partially_received: "bg-yellow-500/20 text-yellow-300",
  received: "bg-emerald-500/20 text-emerald-300",
  cancelled: "bg-rose-500/20 text-rose-300",
};

const STATUS_OPTIONS: PurchaseOrderStatus[] = [
  "draft",
  "sent",
  "confirmed",
  "partially_received",
  "received",
  "cancelled",
];

function StatusBadge({ status }: { status: PurchaseOrderStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[status]}`}
    >
      {status.replace(/_/g, " ")}
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

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | PurchaseOrderStatus>("all");
  const [sortField, setSortField] = useState<"po_number" | "total_cost" | "created_at">(
    "created_at"
  );
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [selectedOrder, setSelectedOrder] = useState<PurchaseOrder | null>(null);
  const [pendingStatus, setPendingStatus] = useState<PurchaseOrderStatus | "">("");
  const [isSavingStatus, setIsSavingStatus] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    supplier_id: "",
    expected_date: "",
    notes: "",
  });

  const PAGE_SIZE = 20;

  useEffect(() => {
    loadData();
  }, [page]);

  async function loadData() {
    setIsLoading(true);
    setError(null);
    try {
      const [ordersRes, suppRes] = await Promise.all([
        apiRequest<PurchaseOrderListResponse>(
          `/api/v1/purchase-orders?skip=${(page - 1) * PAGE_SIZE}&limit=${PAGE_SIZE}`
        ),
        apiRequest<SupplierListResponse>(`/api/v1/suppliers?skip=0&limit=200`),
      ]);
      setOrders(ordersRes.items);
      setTotal(ordersRes.total);
      setSuppliers(suppRes.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load purchase orders");
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
    let filtered = orders;
    if (activeFilter !== "all") {
      filtered = filtered.filter((o) => o.status === activeFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (o) =>
          o.po_number.toLowerCase().includes(q) ||
          supplierName(o.supplier_id).toLowerCase().includes(q)
      );
    }
    return [...filtered].sort((a, b) => {
      let av: string | number, bv: string | number;
      if (sortField === "total_cost") {
        av = parseFloat(a.total_cost);
        bv = parseFloat(b.total_cost);
      } else {
        av = a[sortField] ?? "";
        bv = b[sortField] ?? "";
      }
      if (av < bv) return sortDirection === "asc" ? -1 : 1;
      if (av > bv) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [orders, activeFilter, search, sortField, sortDirection, suppliers]);

  function toggleSort(field: typeof sortField) {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  }

  function SortIndicator({ field }: { field: typeof sortField }) {
    if (sortField !== field) return <span className="ml-1 text-[#555]">↕</span>;
    return (
      <span className="ml-1 text-[#888]">{sortDirection === "asc" ? "↑" : "↓"}</span>
    );
  }

  function openOrder(order: PurchaseOrder) {
    setSelectedOrder(order);
    setPendingStatus(order.status);
  }

  function closePanel() {
    setSelectedOrder(null);
    setPendingStatus("");
  }

  async function handleStatusUpdate() {
    if (!selectedOrder || !pendingStatus || pendingStatus === selectedOrder.status) return;
    setIsSavingStatus(true);
    try {
      const updated = await apiRequest<PurchaseOrder>(
        `/api/v1/purchase-orders/${selectedOrder.id}`,
        {
          method: "PATCH",
          body: { status: pendingStatus },
        }
      );
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
      setSelectedOrder(updated);
      setPendingStatus(updated.status);
      flash("Status updated successfully");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    } finally {
      setIsSavingStatus(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingCreate(true);
    try {
      const body: Record<string, unknown> = {};
      if (createForm.supplier_id) body.supplier_id = createForm.supplier_id;
      if (createForm.expected_date) body.expected_date = createForm.expected_date;
      if (createForm.notes) body.notes = createForm.notes;
      const created = await apiRequest<PurchaseOrder>("/api/v1/purchase-orders", {
        method: "POST",
        body,
      });
      setOrders((prev) => [created, ...prev]);
      setTotal((t) => t + 1);
      setIsCreateOpen(false);
      setCreateForm({ supplier_id: "", expected_date: "", notes: "" });
      flash("Purchase order created");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create order");
    } finally {
      setIsSavingCreate(false);
    }
  }

  function flash(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Purchase Orders</h1>
          <p className="mt-1 text-sm text-[#888]">{total} order{total !== 1 ? "s" : ""} total</p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90"
        >
          + New PO
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
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search by PO # or supplier…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 rounded-md border border-[#333] px-3 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50 w-64"
        />
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
              {s.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-[#222] bg-[#141414] shadow-sm">
        <table className="min-w-full divide-y divide-[#222]">
          <thead className="bg-[#1a1a1a]">
            <tr>
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider select-none"
                onClick={() => toggleSort("po_number")}
              >
                PO # <SortIndicator field="po_number" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Supplier
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Status
              </th>
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider select-none"
                onClick={() => toggleSort("total_cost")}
              >
                Total Cost <SortIndicator field="total_cost" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Items
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Expected
              </th>
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider select-none"
                onClick={() => toggleSort("created_at")}
              >
                Created <SortIndicator field="created_at" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#222]">
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-[#888]">
                  Loading…
                </td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-[#888]">
                  No purchase orders found.
                </td>
              </tr>
            ) : (
              visible.map((order) => (
                <tr
                  key={order.id}
                  className="cursor-pointer hover:bg-white/[0.02] transition-colors"
                  onClick={() => openOrder(order)}
                >
                  <td className="px-4 py-3 text-sm font-mono font-medium text-white">
                    {order.po_number}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#aaa]">
                    {supplierName(order.supplier_id)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={order.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-[#aaa] font-medium">
                    {fmt(order.total_cost)}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#888]">
                    {order.line_items?.length ?? 0}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#888]">
                    {order.expected_date
                      ? new Date(order.expected_date).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#888]">
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-[#888]">
          <span>
            Page {page} of {totalPages}
          </span>
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

      {/* Create PO Panel */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={() => setIsCreateOpen(false)} />
          <div className="w-full max-w-md bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <h2 className="text-lg font-semibold text-white">New Purchase Order</h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-[#666] hover:text-[#aaa] text-xl leading-none"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCreate} className="flex-1 space-y-5 px-6 py-5">
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Supplier</label>
                <select
                  value={createForm.supplier_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, supplier_id: e.target.value }))}
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                >
                  <option value="">— No supplier —</option>
                  {suppliers
                    .filter((s) => s.is_active)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">
                  Expected Delivery Date
                </label>
                <input
                  type="date"
                  value={createForm.expected_date}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, expected_date: e.target.value }))
                  }
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Notes</label>
                <textarea
                  value={createForm.notes}
                  onChange={(e) => setCreateForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={3}
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                />
              </div>
              <p className="text-xs text-[#888]">
                Line items can be added after PO creation via the API.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={isSavingCreate}
                  className="flex-1 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:opacity-60"
                >
                  {isSavingCreate ? "Creating…" : "Create PO"}
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

      {/* PO Detail Panel */}
      {selectedOrder && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={closePanel} />
          <div className="w-full max-w-xl bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-white font-mono">
                  {selectedOrder.po_number}
                </h2>
                <StatusBadge status={selectedOrder.status} />
              </div>
              <button
                onClick={closePanel}
                className="text-[#666] hover:text-[#aaa] text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="flex-1 space-y-6 px-6 py-5">
              {/* Summary */}
              <dl className="grid grid-cols-2 gap-4">
                <DetailItem label="Supplier" value={supplierName(selectedOrder.supplier_id)} />
                <DetailItem label="Total Cost" value={fmt(selectedOrder.total_cost)} />
                <DetailItem
                  label="Order Date"
                  value={
                    selectedOrder.order_date
                      ? new Date(selectedOrder.order_date).toLocaleDateString()
                      : "—"
                  }
                />
                <DetailItem
                  label="Expected Date"
                  value={
                    selectedOrder.expected_date
                      ? new Date(selectedOrder.expected_date).toLocaleDateString()
                      : "—"
                  }
                />
                <DetailItem
                  label="Received Date"
                  value={
                    selectedOrder.received_date
                      ? new Date(selectedOrder.received_date).toLocaleDateString()
                      : "—"
                  }
                />
                <DetailItem
                  label="Created"
                  value={new Date(selectedOrder.created_at).toLocaleString()}
                />
              </dl>

              {selectedOrder.notes && (
                <div>
                  <dt className="text-xs font-medium text-[#888] uppercase tracking-wide">
                    Notes
                  </dt>
                  <dd className="mt-1 text-sm text-[#aaa] whitespace-pre-wrap">
                    {selectedOrder.notes}
                  </dd>
                </div>
              )}

              {/* Line Items */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">
                  Line Items ({selectedOrder.line_items?.length ?? 0})
                </h3>
                {!selectedOrder.line_items || selectedOrder.line_items.length === 0 ? (
                  <p className="text-sm text-[#666] italic">No line items.</p>
                ) : (
                  <div className="overflow-hidden rounded-lg border border-[#222]">
                    <table className="min-w-full divide-y divide-[#222] text-sm">
                      <thead className="bg-[#1a1a1a]">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-[#888] uppercase">
                            Product
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Ordered
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Received
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Unit Cost
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Subtotal
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#222]">
                        {selectedOrder.line_items.map((item: POLineItem) => (
                          <tr key={item.id}>
                            <td className="px-3 py-2 text-[#aaa] font-mono text-xs">
                              {item.product_id ? item.product_id.slice(0, 8) + "…" : "—"}
                            </td>
                            <td className="px-3 py-2 text-right text-[#aaa]">
                              {item.quantity_ordered}
                            </td>
                            <td className="px-3 py-2 text-right text-[#aaa]">
                              <span
                                className={
                                  item.quantity_received >= item.quantity_ordered
                                    ? "text-emerald-400 font-medium"
                                    : item.quantity_received > 0
                                    ? "text-yellow-400"
                                    : "text-[#888]"
                                }
                              >
                                {item.quantity_received}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right text-[#aaa]">
                              {fmt(item.unit_cost)}
                            </td>
                            <td className="px-3 py-2 text-right font-medium text-white">
                              {fmt(item.subtotal)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-[#1a1a1a]">
                        <tr>
                          <td
                            colSpan={4}
                            className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase"
                          >
                            Total
                          </td>
                          <td className="px-3 py-2 text-right font-semibold text-white">
                            {fmt(selectedOrder.total_cost)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </div>

              {/* Status Update */}
              <div className="border-t border-[#222] pt-5">
                <h3 className="text-sm font-medium text-white mb-3">Update Status</h3>
                <div className="flex gap-3 items-center">
                  <select
                    value={pendingStatus}
                    onChange={(e) => setPendingStatus(e.target.value as PurchaseOrderStatus)}
                    className="flex-1 rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50 capitalize"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleStatusUpdate}
                    disabled={
                      isSavingStatus ||
                      !pendingStatus ||
                      pendingStatus === selectedOrder.status
                    }
                    className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:opacity-60 whitespace-nowrap"
                  >
                    {isSavingStatus ? "Saving…" : "Update Status"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
