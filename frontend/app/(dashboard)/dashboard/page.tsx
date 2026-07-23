"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getCurrentUser } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import { AppTileIcon } from "@/components/AppTileIcon";
import { OnboardingChecklist } from "@/components/onboarding/OnboardingChecklist";
import type { DashboardMetricsResponse, UserRole } from "@/types/api";

const REFRESH_INTERVAL = 30;
type FetchState = "idle" | "loading" | "refreshing" | "error";

// ── Formatting helpers ─────────────────────────────────────────────────────

function fmt(n: string | number, decimals = 0) {
  return Number(n).toLocaleString("en-ZA", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
function fmtCurrency(n: string | number) {
  return `R ${fmt(n, 2)}`;
}

// ── Stat card ──────────────────────────────────────────────────────────────

type Accent = "green" | "blue" | "amber" | "red" | "violet" | "none";

const ACCENT_STYLES: Record<Accent, { dot: string; badge: string }> = {
  green:  { dot: "bg-emerald-400 text-emerald-400", badge: "bg-emerald-950 text-emerald-300" },
  blue:   { dot: "bg-blue-400 text-blue-400",       badge: "bg-blue-950   text-blue-300"   },
  amber:  { dot: "bg-amber-400 text-amber-400",     badge: "bg-amber-950  text-amber-300"  },
  red:    { dot: "bg-red-400 text-red-400",         badge: "bg-red-950    text-red-300"    },
  violet: { dot: "bg-violet-400 text-violet-400",   badge: "bg-violet-950 text-violet-300" },
  none:   { dot: "",                                 badge: "bg-[#1f1f1f]  text-[#888]"    },
};

function StatCard({
  label, value, sub, accent = "none", badge, trend,
}: {
  label: string; value: string | number; sub?: string;
  accent?: Accent; badge?: string;
  trend?: { pct: number; label: string };
}) {
  const a = ACCENT_STYLES[accent];
  return (
    <div className="erp-panel">
      {a.dot && <span className={`status-dot ${a.dot}`} />}
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
          {badge && (
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${a.badge}`}>
              {badge}
            </span>
          )}
        </div>
        <p className="mt-2 text-2xl font-bold tracking-tight text-white">{value}</p>
        <div className="mt-1 flex items-center gap-2">
          {sub && <p className="text-[11px] text-muted">{sub}</p>}
          {trend && (
            <span className={`text-[11px] font-medium ${trend.pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {trend.pct >= 0 ? "▲" : "▼"} {Math.abs(trend.pct).toFixed(1)}% {trend.label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title, icon }: { title: string; icon: string }) {
  return (
    <div className="flex items-center gap-2">
      <AppTileIcon name={icon} className="h-4 w-4 text-tertiary-fixed-dim" />
      <h2 className="text-sm font-semibold text-[#aaa]">{title}</h2>
    </div>
  );
}

function AlertRow({ count, label, href }: { count: number; label: string; href?: string }) {
  if (count === 0) return null;
  const inner = (
    <div className="flex items-center gap-3 rounded-lg border border-red-900/40 bg-red-950/30 px-4 py-2.5">
      <span className="h-2 w-2 rounded-full bg-red-500" />
      <p className="text-sm text-red-400">
        <strong className="font-semibold">{count}</strong> {label}
      </p>
      {href && <span className="ml-auto text-xs font-medium text-red-400 underline underline-offset-2">View →</span>}
    </div>
  );
  return href ? <a href={href}>{inner}</a> : inner;
}

// ── Sparkline (inline SVG — no external library) ──────────────────────────

function Sparkline({ values, accent = "green" }: { values: number[]; accent?: "green" | "red" }) {
  if (values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const W = 80; const H = 28;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / range) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const color = accent === "green" ? "#10b981" : "#f87171";
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none" className="shrink-0 opacity-70">
      <polyline points={pts} stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Quick Actions ──────────────────────────────────────────────────────────

function QuickActions() {
  const actions = [
    { label: "New Invoice",   icon: "receipt_long",   href: "/invoices" },
    { label: "Add Customer",  icon: "person_add",     href: "/leads" },
    { label: "New Task",      icon: "add_task",       href: "/tasks" },
    { label: "Add Expense",   icon: "payments",       href: "/finance" },
    { label: "Add Employee",  icon: "badge",          href: "/employees" },
    { label: "New Product",   icon: "inventory_2",    href: "/inventory" },
  ];
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
      {actions.map((a) => (
        <Link
          key={a.label}
          href={a.href}
          className="erp-panel flex flex-col items-center gap-1.5 px-2 py-3 text-center transition-colors hover:border-tertiary-fixed-dim/40"
        >
          <AppTileIcon name={a.icon} className="h-5 w-5 text-tertiary-fixed-dim" />
          <span className="text-[10px] font-medium text-muted leading-tight">{a.label}</span>
        </Link>
      ))}
    </div>
  );
}

interface HRStats  { employees: number; pendingLeave: number }
interface FinStats { revenue: number; expenses: number; netProfit: number; prevRevenue?: number; prevExpenses?: number }
interface InvStats { total: number; outstanding: number }

// ── Page ───────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetricsResponse | null>(null);
  const [state, setState] = useState<FetchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
  const [role, setRole] = useState<UserRole | null>(null);
  const [hrStats, setHrStats]   = useState<HRStats | null>(null);
  const [finStats, setFinStats] = useState<FinStats | null>(null);
  const [invStats, setInvStats] = useState<InvStats | null>(null);

  const fetchMetrics = useCallback(async (trigger: "initial" | "manual" | "auto") => {
    setState((prev) => trigger === "initial" && prev === "idle" ? "loading" : "refreshing");
    setError(null);

    try {
      const res = await fetch("/api/dashboard-metrics", {
        headers: { Accept: "application/json" },
        credentials: "include",
        cache: "no-store",
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error((payload as { detail?: string })?.detail ?? "Unable to load dashboard");
      }
      setMetrics(payload as DashboardMetricsResponse);
      setState("idle");
      setCountdown(REFRESH_INTERVAL);
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "Unable to load dashboard");
    }
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => void fetchMetrics("initial"), 0);
    return () => window.clearTimeout(t);
  }, [fetchMetrics]);

  useEffect(() => {
    if (!metrics) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "hidden") return;
      setCountdown((prev) => {
        if (prev <= 1) { void fetchMetrics("auto"); return REFRESH_INTERVAL; }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(t);
  }, [fetchMetrics, metrics]);

  useEffect(() => {
    getCurrentUser().then((u) => {
      setRole(u.role);
      if (u.role === "owner" || u.role === "manager") {
        Promise.all([
          apiRequest<{ items: unknown[]; total: number }>("/api/v1/hr/employees?limit=1"),
          apiRequest<{ items: unknown[]; total: number }>("/api/v1/hr/leave-requests?status=pending&limit=1"),
          apiRequest<{ revenue: number; expenses: number; net_profit: number }>("/api/v1/finance/summary?period=this_month"),
          apiRequest<{ revenue: number; expenses: number; net_profit: number }>("/api/v1/finance/summary?period=last_month"),
          apiRequest<{ items: { status: string; total_amount: number }[]; total: number }>("/api/v1/invoices?limit=50"),
        ]).then(([emp, leave, fin, finPrev, invList]) => {
          setHrStats({ employees: emp.total, pendingLeave: leave.total });
          setFinStats({
            revenue: fin.revenue,
            expenses: fin.expenses,
            netProfit: fin.net_profit,
            prevRevenue: finPrev.revenue,
            prevExpenses: finPrev.expenses,
          });
          const outstanding = invList.items
            .filter((i) => i.status === "sent" || i.status === "overdue")
            .reduce((s, i) => s + Number(i.total_amount), 0);
          setInvStats({ total: invList.total, outstanding });
        }).catch(() => null);
      }
    }).catch(() => null);
  }, []);

  const loading = state === "loading" && !metrics;
  const ph = (v: string | number) => (loading ? "—" : v);
  const isStaff = role === "staff";

  const s   = metrics?.sales;
  const l   = metrics?.leads;
  const t   = metrics?.tasks;
  const inv = metrics?.inventory;
  const wf  = metrics?.workflows;

  // Trend helpers
  function trendPct(current: number, previous: number) {
    if (!previous) return null;
    return { pct: ((current - previous) / previous) * 100, label: "vs last month" };
  }

  // Attention items
  const attentionItems: { label: string; href: string; severity: "red" | "amber" }[] = [];
  if ((t?.overdue ?? 0) > 0)                  attentionItems.push({ label: `${t!.overdue} overdue tasks`, href: "/tasks",     severity: "red" });
  if ((inv?.out_of_stock_products ?? 0) > 0)  attentionItems.push({ label: `${inv!.out_of_stock_products} out-of-stock products`, href: "/inventory", severity: "red" });
  if ((wf?.failed_runs_today ?? 0) > 0)       attentionItems.push({ label: `${wf!.failed_runs_today} workflow failures today`, href: "/runs",      severity: "red" });
  if ((inv?.low_stock_products ?? 0) > 0)     attentionItems.push({ label: `${inv!.low_stock_products} products low on stock`,  href: "/inventory", severity: "amber" });
  if ((hrStats?.pendingLeave ?? 0) > 0)       attentionItems.push({ label: `${hrStats!.pendingLeave} pending leave requests`,   href: "/leave",     severity: "amber" });

  return (
    <div className="space-y-8">

      {/* ── Page header ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="mt-0.5 text-xs text-muted">
            Auto-refreshes every {REFRESH_INTERVAL}s
            {metrics && <> · last updated {new Date(metrics.refreshedAt).toLocaleTimeString()}</>}
            {state !== "loading" && <> · next in <strong className="text-[#aaa]">{countdown}s</strong></>}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void fetchMetrics("manual")}
          disabled={state === "refreshing"}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-[#aaa] shadow-sm hover:bg-[#1f1f1f] disabled:opacity-50"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
          {state === "refreshing" ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* ── Error ──────────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {error}
          <button
            type="button"
            onClick={() => void fetchMetrics("manual")}
            className="ml-4 rounded border border-red-800 px-2 py-0.5 text-xs hover:bg-red-950"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Getting Started ────────────────────────────────────────────── */}
      <OnboardingChecklist />

      {/* ── Quick Actions ───────────────────────────────────────────────── */}
      <div className="space-y-3">
        <SectionHeader title="Quick Actions" icon="bolt" />
        <QuickActions />
      </div>

      {/* ── Attention Required ─────────────────────────────────────────── */}
      {!loading && attentionItems.length > 0 && (
        <div className="space-y-2">
          <SectionHeader title="Attention Required" icon="notifications" />
          <div className="space-y-1.5">
            {attentionItems.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 transition-opacity hover:opacity-90 ${
                  item.severity === "red"
                    ? "border-red-900/40 bg-red-950/30"
                    : "border-amber-900/40 bg-amber-950/20"
                }`}
              >
                <span className={`h-2 w-2 shrink-0 rounded-full ${item.severity === "red" ? "bg-red-500" : "bg-amber-400"}`} />
                <p className={`text-sm ${item.severity === "red" ? "text-red-400" : "text-amber-300"}`}>{item.label}</p>
                <span className={`ml-auto text-xs underline underline-offset-2 ${item.severity === "red" ? "text-red-400" : "text-amber-300"}`}>
                  View →
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ── Staff-only: simplified Tasks view ──────────────────────────── */}
      {isStaff && (
        <div className="space-y-3">
          <SectionHeader title="My Tasks" icon="task_alt" />
          <div className="grid grid-cols-3 gap-4">
            <StatCard
              label="Overdue"
              value={ph(fmt(t?.overdue ?? 0))}
              accent={(t?.overdue ?? 0) > 0 ? "red" : "none"}
              badge={(t?.overdue ?? 0) > 0 ? "!" : undefined}
            />
            <StatCard
              label="Due Today"
              value={ph(fmt(t?.due_today ?? 0))}
              accent={(t?.due_today ?? 0) > 0 ? "amber" : "none"}
            />
            <StatCard label="Pending" value={ph(fmt(t?.pending ?? 0))} />
          </div>
          <p className="text-xs text-muted">
            Contact a manager to view finance, inventory, and HR data.
          </p>
        </div>
      )}

      {/* ── Owner / Manager: full dashboard ─────────────────────────────── */}
      {!isStaff && (
        <>
          {/* ── Finance (This Month) with trends ── */}
          {finStats && (
            <div className="space-y-3">
              <SectionHeader title="Finance — This Month" icon="analytics" />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard
                  label="Revenue"
                  value={fmtCurrency(finStats.revenue)}
                  accent="green"
                  trend={finStats.prevRevenue !== undefined ? (trendPct(finStats.revenue, finStats.prevRevenue) ?? undefined) : undefined}
                />
                <StatCard
                  label="Expenses"
                  value={fmtCurrency(finStats.expenses)}
                  accent="red"
                  trend={finStats.prevExpenses !== undefined ? (trendPct(finStats.expenses, finStats.prevExpenses) ?? undefined) : undefined}
                />
                <StatCard
                  label="Net Profit"
                  value={fmtCurrency(finStats.netProfit)}
                  accent={finStats.netProfit >= 0 ? "blue" : "red"}
                />
              </div>
            </div>
          )}

          {/* ── Sales ── */}
          <div className="space-y-3">
            <SectionHeader title="Sales" icon="payments" />
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <StatCard label="Total Revenue"      value={ph(fmtCurrency(s?.revenue_total ?? 0))}       accent="green" />
              <StatCard label="Revenue This Month" value={ph(fmtCurrency(s?.revenue_this_month ?? 0))}  accent="green" />
              <StatCard
                label="Open Orders"
                value={ph(fmt(s?.open_orders ?? 0))}
                sub="draft · confirmed · processing"
                accent="blue"
                badge={s?.open_orders ? String(s.open_orders) : undefined}
              />
              <StatCard label="Total Orders" value={ph(fmt(s?.orders_total ?? 0))} />
            </div>
          </div>

          {/* ── Leads & Tasks ── */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <SectionHeader title="Leads" icon="groups" />
              <div className="grid grid-cols-2 gap-4">
                <StatCard label="Open Leads"  value={ph(fmt(l?.open_leads ?? 0))}      accent="blue"  badge={l?.open_leads ? String(l.open_leads) : undefined} />
                <StatCard label="New"         value={ph(fmt(l?.new_leads ?? 0))}        accent="violet" />
                <StatCard label="Qualified"   value={ph(fmt(l?.qualified_leads ?? 0))}  />
                <StatCard label="Won"         value={ph(fmt(l?.won_leads ?? 0))}        accent="green" />
              </div>
            </div>

            <div className="space-y-3">
              <SectionHeader title="Tasks" icon="task_alt" />
              <div className="grid grid-cols-3 gap-4">
                <StatCard
                  label="Overdue"
                  value={ph(fmt(t?.overdue ?? 0))}
                  accent={(t?.overdue ?? 0) > 0 ? "red" : "none"}
                  badge={(t?.overdue ?? 0) > 0 ? "!" : undefined}
                />
                <StatCard
                  label="Due Today"
                  value={ph(fmt(t?.due_today ?? 0))}
                  accent={(t?.due_today ?? 0) > 0 ? "amber" : "none"}
                />
                <StatCard label="Pending" value={ph(fmt(t?.pending ?? 0))} />
              </div>
            </div>
          </div>

          {/* ── Inventory & Workflows ── */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <SectionHeader title="Inventory" icon="inventory_2" />
              <div className="grid grid-cols-2 gap-4">
                <StatCard
                  label="Low Stock"
                  value={ph(fmt(inv?.low_stock_products ?? 0))}
                  accent={(inv?.low_stock_products ?? 0) > 0 ? "amber" : "none"}
                  badge={(inv?.low_stock_products ?? 0) > 0 ? "Low" : undefined}
                />
                <StatCard
                  label="Out of Stock"
                  value={ph(fmt(inv?.out_of_stock_products ?? 0))}
                  accent={(inv?.out_of_stock_products ?? 0) > 0 ? "red" : "none"}
                  badge={(inv?.out_of_stock_products ?? 0) > 0 ? "!" : undefined}
                />
                <StatCard label="Active Products"  value={ph(fmt(inv?.total_active_products ?? 0))} />
                <StatCard label="Active Suppliers" value={ph(fmt(inv?.total_suppliers ?? 0))} />
              </div>
            </div>

            <div className="space-y-3">
              <SectionHeader title="Workflows" icon="bolt" />
              <div className="grid grid-cols-3 gap-4">
                <StatCard label="Definitions" value={ph(fmt(wf?.total_definitions ?? 0))} />
                <StatCard
                  label="Active Runs"
                  value={ph(fmt(wf?.active_runs ?? 0))}
                  accent={(wf?.active_runs ?? 0) > 0 ? "blue" : "none"}
                />
                <StatCard
                  label="Failures Today"
                  value={ph(fmt(wf?.failed_runs_today ?? 0))}
                  accent={(wf?.failed_runs_today ?? 0) > 0 ? "red" : "none"}
                  badge={(wf?.failed_runs_today ?? 0) > 0 ? "!" : undefined}
                />
              </div>
            </div>
          </div>

          {/* ── HR & Invoices ── */}
          {(hrStats || invStats) && (
            <div className="grid gap-6 lg:grid-cols-2">
              {hrStats && (
                <div className="space-y-3">
                  <SectionHeader title="HR" icon="groups" />
                  <div className="grid grid-cols-2 gap-4">
                    <StatCard label="Employees" value={fmt(hrStats.employees)} accent="blue" />
                    <StatCard
                      label="Pending Leave"
                      value={fmt(hrStats.pendingLeave)}
                      accent={hrStats.pendingLeave > 0 ? "amber" : "none"}
                      badge={hrStats.pendingLeave > 0 ? String(hrStats.pendingLeave) : undefined}
                    />
                  </div>
                </div>
              )}
              {invStats && (
                <div className="space-y-3">
                  <SectionHeader title="Invoices" icon="receipt_long" />
                  <div className="grid grid-cols-2 gap-4">
                    <StatCard label="Total"       value={fmt(invStats.total)}                    accent="violet" />
                    <StatCard label="Outstanding" value={fmtCurrency(invStats.outstanding)} accent={invStats.outstanding > 0 ? "amber" : "none"} />
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

    </div>
  );
}
