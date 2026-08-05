"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { UserPlatformListResponse } from "@/types/api";

const PAGE_SIZE = 50;

const TIER_LABELS: Record<string, string> = {
  trial: "Trial",
  starter: "Starter",
  growth: "Growth",
  professional: "Professional",
  enterprise: "Enterprise",
  legacy: "Legacy",
};

function planBadge(tier: string) {
  if (tier === "trial") return "bg-amber-500/15 text-amber-300";
  if (tier === "legacy") return "bg-white/10 text-[#999]";
  return "bg-emerald-500/15 text-emerald-300";
}

export default function PlatformUsersPage() {
  const [data, setData] = useState<UserPlatformListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  function load(p: number) {
    platformApiRequest<UserPlatformListResponse>("/platform/v1/users", {
      query: { skip: (p - 1) * PAGE_SIZE, limit: PAGE_SIZE },
    })
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load users"));
  }

  useEffect(() => load(page), [page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Users</h1>
        {data && <p className="text-sm text-[#777]">{data.total} total</p>}
      </div>

      {error && (
        <p className="mb-4 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-xl border border-[#22222e]">
        <table className="w-full text-left text-sm">
          <thead className="bg-[#12121a] text-[11px] uppercase tracking-wide text-[#777]">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Role</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((u) => (
              <tr key={u.id} className="border-t border-[#1c1c26] hover:bg-white/[0.02]">
                <td className="px-4 py-3 text-white">{u.full_name}</td>
                <td className="px-4 py-3 text-[#ccc]">{u.email}</td>
                <td className="px-4 py-3">
                  <Link href={`/platform/organizations/${u.organization_id}`} className="text-violet-300 hover:underline">
                    {u.business_name}
                  </Link>
                  <p className="text-xs text-[#666]">{u.organization_name}</p>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${planBadge(u.plan_tier)}`}>
                    {TIER_LABELS[u.plan_tier] ?? u.plan_tier}
                  </span>
                  <p className="mt-0.5 text-xs capitalize text-[#666]">{u.subscription_status}</p>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      u.is_active ? "bg-emerald-500/15 text-emerald-300" : "bg-white/10 text-[#999]"
                    }`}
                  >
                    {u.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 capitalize text-[#ccc]">{u.role.replace("_", " ")}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-[#666]">
                  No users yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-[#777]">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-md border border-[#2a2a3a] px-3 py-1.5 text-xs text-[#aaa] hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-md border border-[#2a2a3a] px-3 py-1.5 text-xs text-[#aaa] hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
