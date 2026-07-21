"use client";

import { useState } from "react";
import { useUser } from "@/contexts/UserContext";

const UPGRADE_URL = "https://mmnexus.co.za/biznizflowpilot#pricing";

/** Persistent, non-dismissible strip shown on every dashboard page for a
 * trial account: days remaining + upgrade CTA, plus a disclaimer that this
 * workspace's data is sample data seeded at signup, not real business
 * records. Renders nothing for non-trial (paying/legacy) accounts. */
export function TrialBanner() {
  const { user } = useUser();
  const [nowMs] = useState(() => Date.now());

  if (!user || user.plan_tier !== "trial") return null;

  const daysLeft = user.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(user.trial_ends_at).getTime() - nowMs) / 86_400_000))
    : null;

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-brand/40 bg-brand px-4 py-2 text-center text-xs font-medium text-on-primary sm:text-sm">
      <span>
        {daysLeft !== null ? (
          <>🎉 Free trial &mdash; {daysLeft} day{daysLeft === 1 ? "" : "s"} left.</>
        ) : (
          <>🎉 You&apos;re on a free trial.</>
        )}{" "}
        This workspace is pre-loaded with sample data so you can explore every feature.
      </span>
      <a
        href={UPGRADE_URL}
        className="shrink-0 rounded-md bg-on-primary/15 px-3 py-1 text-xs font-semibold transition-colors hover:bg-on-primary/25"
      >
        Upgrade now
      </a>
    </div>
  );
}
