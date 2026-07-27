"use client";

import { useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { PlatformStats } from "@/types/api";

const BUSINESS_CARDS: { key: keyof PlatformStats; label: string }[] = [
  { key: "total_organizations", label: "Organizations" },
  { key: "total_tenants", label: "Subsidiaries" },
  { key: "total_users", label: "Total users" },
  { key: "active_users", label: "Active users" },
];

const OPS_CARDS: { key: keyof PlatformStats; label: string }[] = [
  { key: "total_events", label: "Events logged" },
  { key: "total_workflow_runs", label: "Workflow runs" },
  { key: "workflow_runs_failed", label: "Failed runs" },
];

const TIER_LABELS: Record<string, string> = {
  trial: "Trial",
  starter: "Starter",
  growth: "Growth",
  professional: "Professional",
  enterprise: "Enterprise",
  legacy: "Legacy",
};

const TIER_ORDER = ["trial", "starter", "growth", "professional", "enterprise", "legacy"];

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-label-caps text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

export default function PlatformOverviewPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformApiRequest<PlatformStats>("/platform/v1/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load stats"));
  }, []);

  const tierEntries = stats
    ? TIER_ORDER.filter((tier) => stats.organizations_by_plan_tier[tier] !== undefined)
    : [];

  return (
    <div>
      <h1 className="text-h1 mb-6 text-foreground">Overview</h1>

      {error && (
        <p className="mb-4 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      {/* ── Revenue & conversion ── */}
      <p className="text-label-caps mb-2 text-muted">Revenue</p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <StatTile
          label="MRR (estimate)"
          value={stats ? `R${stats.mrr_zar.toLocaleString("en-ZA")}` : "—"}
        />
        <StatTile
          label="Trial → paid conversion"
          value={
            stats && stats.trial_conversion_rate !== null
              ? `${(stats.trial_conversion_rate * 100).toFixed(0)}%`
              : "—"
          }
        />
      </div>

      {/* ── Organizations by plan ── */}
      <p className="text-label-caps mb-2 mt-8 text-muted">Organizations by plan</p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {tierEntries.length > 0
          ? tierEntries.map((tier) => (
              <StatTile
                key={tier}
                label={TIER_LABELS[tier] ?? tier}
                value={stats?.organizations_by_plan_tier[tier] ?? 0}
              />
            ))
          : [0, 1, 2].map((i) => <StatTile key={i} label="—" value="—" />)}
      </div>

      {/* ── Business ── */}
      <p className="text-label-caps mb-2 mt-8 text-muted">Business</p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {BUSINESS_CARDS.map((card) => (
          <StatTile key={card.key} label={card.label} value={stats ? (stats[card.key] as number) : "—"} />
        ))}
      </div>

      {/* ── Operations ── */}
      <p className="text-label-caps mb-2 mt-8 text-muted">Operations</p>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {OPS_CARDS.map((card) => (
          <StatTile key={card.key} label={card.label} value={stats ? (stats[card.key] as number) : "—"} />
        ))}
      </div>
    </div>
  );
}
