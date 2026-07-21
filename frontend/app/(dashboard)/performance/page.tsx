"use client";

import { PageHeader } from "@/components/PageHeader";
import { HRSubNav } from "@/components/HRSubNav";

export default function PerformancePage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      <PageHeader title="Performance & Productivity" subtitle="Reviews, goals, and productivity tracking" />
      <div className="erp-panel flex flex-col items-center justify-center gap-2 py-16 text-center">
        <span className="material-symbols-outlined text-4xl text-on-surface-variant">trending_up</span>
        <p className="text-sm font-medium text-surface-bright">Coming soon</p>
        <p className="max-w-sm text-[13px] text-on-surface-variant">
          Performance reviews and productivity tracking aren&apos;t built yet. This tab is here to hold its place in the HR hub.
        </p>
      </div>
    </div>
  );
}
