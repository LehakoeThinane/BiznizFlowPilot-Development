"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { Pagination } from "@/components/Pagination";
import type { BusinessEvent, EventListResponse } from "@/types/api";

const PAGE_SIZE = 50;

const EVENT_TYPE_LABELS: Record<string, string> = {
  lead_created: "Lead Created", lead_updated: "Lead Updated",
  lead_status_changed: "Lead Status", lead_assigned: "Lead Assigned",
  lead_deleted: "Lead Deleted", lead_idle: "Lead Idle",
  task_created: "Task Created", task_updated: "Task Updated",
  task_assigned: "Task Assigned", task_completed: "Task Completed",
  task_deleted: "Task Deleted", task_overdue: "Task Overdue",
  customer_created: "Customer Created", customer_updated: "Customer Updated",
  customer_deleted: "Customer Deleted",
  product_created: "Product Created", product_updated: "Product Updated",
  product_deleted: "Product Deleted",
  supplier_created: "Supplier Created", supplier_updated: "Supplier Updated",
  supplier_deleted: "Supplier Deleted",
  order_created: "Order Created", order_confirmed: "Order Confirmed",
  order_shipped: "Order Shipped", order_delivered: "Order Delivered",
  order_cancelled: "Order Cancelled",
  stock_low: "Stock Low", stock_adjusted: "Stock Adjusted",
  stock_transferred: "Stock Transferred",
  purchase_order_created: "PO Created", purchase_order_sent: "PO Sent",
  purchase_order_received: "PO Received",
  workflow_triggered: "Workflow", custom: "Custom",
};

function eventColor(type: string): string {
  if (type.startsWith("lead_"))     return "bg-violet-500/20 text-violet-300";
  if (type.startsWith("task_"))     return "bg-blue-500/20 text-blue-300";
  if (type.startsWith("customer_")) return "bg-cyan-500/20 text-cyan-300";
  if (type.startsWith("product_"))  return "bg-orange-500/20 text-orange-300";
  if (type.startsWith("supplier_")) return "bg-yellow-500/20 text-yellow-300";
  if (type.startsWith("order_"))    return "bg-emerald-500/20 text-emerald-300";
  if (type.startsWith("stock_"))    return "bg-amber-500/20 text-amber-300";
  if (type.startsWith("purchase_")) return "bg-teal-500/20 text-teal-300";
  if (type === "workflow_triggered") return "bg-pink-500/20 text-pink-300";
  return "bg-white/10 text-slate-300";
}

function entityLabel(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

const ENTITY_TYPES = ["", "lead", "task", "customer", "product", "supplier",
  "order", "stock_level", "purchase_order", "workflow_run"];

export default function ActivityPage() {
  const [events, setEvents]   = useState<BusinessEvent[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entityFilter, setEntityFilter] = useState("");

  const token = getStoredToken();

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const skip = (page - 1) * PAGE_SIZE;
    const qs = entityFilter ? `&entity_type=${entityFilter}` : "";
    apiRequest<EventListResponse>(
      `/api/v1/events?skip=${skip}&limit=${PAGE_SIZE}${qs}`,
      { authToken: token }
    )
      .then((d) => { setEvents(d.items ?? []); setTotal(d.total ?? 0); })
      .catch((e: unknown) => {
        setEvents([]);
        setTotal(0);
        setError(e instanceof Error ? e.message : "Failed to load activity");
      })
      .finally(() => setLoading(false));
  }, [token, page, entityFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [entityFilter]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Activity Log</h1>
          <p className="mt-1 text-xs text-slate-400">
            All business events — {total} recorded
          </p>
        </div>

        <select
          aria-label="Filter by entity"
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white"
        >
          <option value="">All entities</option>
          {ENTITY_TYPES.filter(Boolean).map((t) => (
            <option key={t} value={t}>{entityLabel(t)}</option>
          ))}
        </select>
      </div>

      <div className="rounded-xl border border-white/6 bg-[#1e293b]">
        {error && (
          <div className="border-b border-red-900/40 bg-red-950/30 px-5 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
        {loading ? (
          <div className="px-5 py-10 text-sm text-slate-400">Loading…</div>
        ) : events.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">
            {error ? "Unable to load events right now." : "No events recorded yet."}
          </div>
        ) : (
          <div className="divide-y divide-white/4">
            {events.map((ev) => (
              <div key={ev.id} className="flex items-start gap-4 px-5 py-3 hover:bg-white/2">
                <div className="mt-0.5 shrink-0">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${eventColor(ev.event_type)}`}>
                    {EVENT_TYPE_LABELS[ev.event_type] ?? ev.event_type}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white truncate">
                    {ev.description ?? `${entityLabel(ev.entity_type)} event`}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {entityLabel(ev.entity_type)} · {ev.entity_id.slice(0, 8)}…
                  </p>
                </div>
                <time className="shrink-0 text-xs text-slate-500 tabular-nums">
                  {formatTime(ev.created_at)}
                </time>
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
    </div>
  );
}
