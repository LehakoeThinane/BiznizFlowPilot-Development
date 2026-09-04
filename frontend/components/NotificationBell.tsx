"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { playNotificationSound, unlockNotificationSound } from "@/lib/notification-sound";

interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  action_url: string | null;
  related_type: string | null;
  related_id: string | null;
  created_at: string;
}

interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread: number;
}

interface NotificationCount { unread: number; total: number }

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function typeColor(type: string) {
  if (type === "leave") return "bg-blue-500";
  if (type === "payroll") return "bg-violet-500";
  if (type === "order_status") return "bg-emerald-500";
  if (type === "low_stock") return "bg-orange-500";
  if (type === "onboarding") return "bg-teal-500";
  return "bg-slate-500";
}

function notificationHref(notification: NotificationItem): string | null {
  if (notification.action_url) return notification.action_url;
  if (!notification.related_type) return null;

  const id = notification.related_id;
  switch (notification.related_type) {
    case "lead":
      return id ? `/leads/${id}` : "/leads";
    case "task":
      return id ? `/tasks/${id}` : "/tasks";
    case "customer":
      return id ? `/customers/${id}` : "/customers";
    case "employee":
      return id ? `/employees/${id}` : "/employees";
    case "invoice":
      return id ? `/invoices/${id}` : "/invoices";
    case "meeting":
      return id ? `/calendar?meeting=${encodeURIComponent(id)}` : "/calendar";
    case "purchase_order":
      return id ? `/purchase-orders/${id}` : "/purchase-orders";
    case "sales_order":
      return id ? `/sales-orders/${id}` : "/sales-orders";
    default:
      return null;
  }
}

export function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const previousUnreadRef = useRef<number | null>(null);

  const fetchCount = useCallback(() => {
    apiRequest<NotificationCount>("/api/v1/notifications/count", {
      _skipRefresh: true,
    })
      .then((d) => {
        if (previousUnreadRef.current !== null && d.unread > previousUnreadRef.current) {
          playNotificationSound();
        }
        previousUnreadRef.current = d.unread;
        setUnread(d.unread);
      })
      .catch(() => null);
  }, []);

  const fetchItems = useCallback(() => {
    setLoading(true);
    apiRequest<NotificationListResponse>("/api/v1/notifications?limit=15", {
      _skipRefresh: true,
    })
      .then((d) => {
        setItems(d.items);
        previousUnreadRef.current = d.unread;
        setUnread(d.unread);
      })
      .catch(() => null)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchCount();
    const interval = setInterval(fetchCount, 30_000);
    return () => clearInterval(interval);
  }, [fetchCount]);

  useEffect(() => {
    if (!open) return;
    fetchItems();
  }, [open, fetchItems]);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function markAllRead() {
    apiRequest("/api/v1/notifications/read-all", {
      method: "PATCH",
      _skipRefresh: true,
    })
      .then(() => {
        setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
        setUnread(0);
      })
      .catch(() => null);
  }

  function markOne(id: string) {
    apiRequest(`/api/v1/notifications/${id}/read`, {
      method: "PATCH",
      _skipRefresh: true,
    })
      .then(() => {
        setItems((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
        setUnread((u) => Math.max(0, u - 1));
      })
      .catch(() => null);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Notifications"
        onClick={() => {
          unlockNotificationSound();
          setOpen((o) => !o);
        }}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-white"
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-80 overflow-hidden rounded-xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
          <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3">
            <p className="text-sm font-semibold text-white">Notifications</p>
            {unread > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-primary-fixed-dim hover:text-white"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-6 text-center text-xs text-slate-500">Loading…</div>
            ) : items.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-slate-500">No notifications yet.</div>
            ) : (
              items.map((n) => (
                <div
                  key={n.id}
                  onClick={() => {
                    if (!n.is_read) markOne(n.id);
                    const href = notificationHref(n);
                    if (href) window.location.href = href;
                  }}
                  className={`flex gap-3 border-b border-outline-variant/60 px-4 py-3 transition-colors hover:bg-surface-container-high ${notificationHref(n) ? "cursor-pointer" : "cursor-default"} ${n.is_read ? "opacity-60" : ""}`}
                >
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${typeColor(n.type)}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{n.title}</p>
                    <p className="mt-0.5 text-[11px] leading-snug text-on-surface-variant">{n.message}</p>
                    <p className="mt-1 text-[10px] text-[#6f7f9a]">{timeAgo(n.created_at)}</p>
                  </div>
                  {!n.is_read && <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-fixed-dim" />}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
