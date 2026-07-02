"use client";

import { useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { PlatformStats } from "@/types/api";

const CARDS: { key: keyof PlatformStats; label: string }[] = [
  { key: "total_organizations", label: "Organizations" },
  { key: "total_tenants", label: "Subsidiaries" },
  { key: "total_users", label: "Total users" },
  { key: "active_users", label: "Active users" },
  { key: "total_events", label: "Events logged" },
  { key: "total_workflow_runs", label: "Workflow runs" },
  { key: "workflow_runs_failed", label: "Failed runs" },
];

export default function PlatformOverviewPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    platformApiRequest<PlatformStats>("/platform/v1/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load stats"));
  }, []);

  return (
    <div>
      <h1 className="mb-6 text-lg font-semibold text-white">Overview</h1>

      {error && (
        <p className="mb-4 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {CARDS.map((card) => (
          <div key={card.key} className="rounded-xl border border-[#22222e] bg-[#12121a] p-4">
            <p className="text-[11px] uppercase tracking-wide text-[#777]">{card.label}</p>
            <p className="mt-1 text-2xl font-semibold text-white">
              {stats ? stats[card.key] : "—"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
