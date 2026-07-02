"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import type {
  SalesOrder,
  SalesOrderListResponse,
  SalesOrderStatus,
  OrderLineItem,
  Customer,
  CustomerListResponse,
} from "@/types/api";

const STATUS_COLORS: Record<SalesOrderStatus, string> = {
  draft: "bg-white/10 text-[#aaa]",
  confirmed: "bg-blue-500/20 text-blue-300",
  processing: "bg-yellow-500/20 text-yellow-300",
  shipped: "bg-purple-500/20 text-purple-300",
  delivered: "bg-emerald-500/20 text-emerald-300",
  cancelled: "bg-rose-500/20 text-rose-300",
};

const STATUS_OPTIONS: SalesOrderStatus[] = [
  "draft",
  "confirmed",
  "processing",
  "shipped",
  "delivered",
  "cancelled",
];

function StatusBadge({ status }: { status: SalesOrderStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_COLORS[status]}`}
    >
      {status.replace("_", " ")}
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

export default function SalesOrdersPage() {
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | SalesOrderStatus>("all");
  const [sortField, setSortField] = useState<"order_number" | "total_amount" | "created_at">(
    "created_at"
  );
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null);
  const [pendingStatus, setPendingStatus] = useState<SalesOrderStatus | "">("");
  const [isSavingStatus, setIsSavingStatus] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    customer_id: "",
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
      const [ordersRes, custRes] = await Promise.all([
        apiRequest<SalesOrderListResponse>(
          `/api/v1/sales-orders?skip=${(page - 1) * PAGE_SIZE}&limit=${PAGE_SIZE}`
        ),
        apiRequest<CustomerListResponse>(`/api/v1/customers?skip=0&limit=200`),
      ]);
      setOrders(ordersRes.items);
      setTotal(ordersRes.total);
      setCustomers(custRes.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load sales orders");
    } finally {
      setIsLoading(false);
    }
  }

  function customerName(id: string | null): string {
    if (!id) return "—";
    const c = customers.find((c) => c.id === id);
    return c ? c.name : id.slice(0, 8) + "…";
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
          o.order_number.toLowerCase().includes(q) ||
          customerName(o.customer_id).toLowerCase().includes(q)
      );
    }
    return [...filtered].sort((a, b) => {
      let av: string | number, bv: string | number;
      if (sortField === "total_amount") {
        av = parseFloat(a.total_amount);
        bv = parseFloat(b.total_amount);
      } else {
        av = a[sortField] ?? "";
        bv = b[sortField] ?? "";
      }
      if (av < bv) return sortDirection === "asc" ? -1 : 1;
      if (av > bv) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [orders, activeFilter, search, sortField, sortDirection, customers]);

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

  function openOrder(order: SalesOrder) {
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
      const updated = await apiRequest<SalesOrder>(
        `/api/v1/sales-orders/${selectedOrder.id}`,
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
      if (createForm.customer_id) body.customer_id = createForm.customer_id;
      if (createForm.notes) body.notes = createForm.notes;
      const created = await apiRequest<SalesOrder>("/api/v1/sales-orders", {
        method: "POST",
        body,
      });
      setOrders((prev) => [created, ...prev]);
      setTotal((t) => t + 1);
      setIsCreateOpen(false);
      setCreateForm({ customer_id: "", notes: "" });
      flash("Sales order created");
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
          <h1 className="text-2xl font-semibold text-white">Sales Orders</h1>
          <p className="mt-1 text-sm text-[#888]">{total} order{total !== 1 ? "s" : ""} total</p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90"
        >
          + New Order
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
          placeholder="Search by order # or customer…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 rounded-md border border-[#333] px-3 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50 w-64"
        />
        <div className="flex gap-1">
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
              {s.replace("_", " ")}
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
                onClick={() => toggleSort("order_number")}
              >
                Order # <SortIndicator field="order_number" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Customer
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Status
              </th>
              <th
                className="cursor-pointer px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider select-none"
                onClick={() => toggleSort("total_amount")}
              >
                Total <SortIndicator field="total_amount" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[#888] uppercase tracking-wider">
                Items
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
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#888]">
                  Loading…
                </td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#888]">
                  No orders found.
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
                    {order.order_number}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#aaa]">
                    {customerName(order.customer_id)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={order.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-[#aaa] font-medium">
                    {fmt(order.total_amount)}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#888]">
                    {order.line_items?.length ?? 0}
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

      {/* Create Order Panel */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={() => setIsCreateOpen(false)} />
          <div className="w-full max-w-md bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <h2 className="text-lg font-semibold text-white">New Sales Order</h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-[#666] hover:text-[#aaa] text-xl leading-none"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCreate} className="flex-1 space-y-5 px-6 py-5">
              <div>
                <label className="block text-xs font-medium text-[#aaa] mb-1">Customer</label>
                <select
                  value={createForm.customer_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, customer_id: e.target.value }))}
                  className="w-full rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                >
                  <option value="">— No customer —</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
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
                Line items can be added after order creation via the API.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={isSavingCreate}
                  className="flex-1 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:opacity-60"
                >
                  {isSavingCreate ? "Creating…" : "Create Order"}
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

      {/* Order Detail Panel */}
      {selectedOrder && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/20" onClick={closePanel} />
          <div className="w-full max-w-xl bg-[#141414] shadow-xl flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#222] px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-white font-mono">
                  {selectedOrder.order_number}
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
                <DetailItem label="Customer" value={customerName(selectedOrder.customer_id)} />
                <DetailItem label="Total Amount" value={fmt(selectedOrder.total_amount)} />
                <DetailItem
                  label="Order Date"
                  value={
                    selectedOrder.order_date
                      ? new Date(selectedOrder.order_date).toLocaleDateString()
                      : "—"
                  }
                />
                <DetailItem
                  label="Tracking #"
                  value={selectedOrder.tracking_number ?? "—"}
                />
                <DetailItem label="Carrier" value={selectedOrder.carrier ?? "—"} />
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
                            Qty
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Unit Price
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase">
                            Subtotal
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#222]">
                        {selectedOrder.line_items.map((item: OrderLineItem) => (
                          <tr key={item.id}>
                            <td className="px-3 py-2 text-[#aaa] font-mono text-xs">
                              {item.product_id ? item.product_id.slice(0, 8) + "…" : "—"}
                            </td>
                            <td className="px-3 py-2 text-right text-[#aaa]">{item.quantity}</td>
                            <td className="px-3 py-2 text-right text-[#aaa]">
                              {fmt(item.unit_price)}
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
                            colSpan={3}
                            className="px-3 py-2 text-right text-xs font-medium text-[#888] uppercase"
                          >
                            Total
                          </td>
                          <td className="px-3 py-2 text-right font-semibold text-white">
                            {fmt(selectedOrder.total_amount)}
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
                    onChange={(e) => setPendingStatus(e.target.value as SalesOrderStatus)}
                    className="flex-1 rounded-md border border-[#333] px-3 py-2 text-sm bg-[#0f0f0f] text-white focus:outline-none focus:ring-2 focus:ring-brand/50"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s.replace("_", " ")}
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
