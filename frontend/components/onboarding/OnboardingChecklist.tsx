"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { ONBOARDING_STEPS } from "@/lib/onboarding-steps";
import { AppTileIcon } from "@/components/AppTileIcon";
import type { OnboardingChecklistResponse, OnboardingStepResponse } from "@/types/api";

const COLLAPSE_KEY = "onboarding-checklist-collapsed";
const GRADUATION_DISMISS_KEY = "onboarding-graduation-dismissed";
const MM_NEXUS_CONTACT_URL = "https://mmnexus.co.za/contact";

/** Tier-aware "getting started" checklist for the dashboard. Steps and their
 * done-state come from the backend (filtered to what the org's plan tier
 * actually unlocks - see app/services/onboarding.py); this component only
 * owns display and the collapse/help interactions. Once every visible step
 * is done, swaps to a dismissible "graduation" card pointing at MM Nexus's
 * custom-systems work - the org has proven out BiznizFlowPilot itself, so
 * this is the moment to surface "need something built on top of this?"
 * rather than just disappearing. Renders nothing if the checklist can't be
 * loaded at all. */
export function OnboardingChecklist() {
  const [steps, setSteps] = useState<OnboardingStepResponse[] | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [helpState, setHelpState] = useState<"idle" | "sending" | "sent">("idle");
  const [graduationDismissed, setGraduationDismissed] = useState(false);

  useEffect(() => {
    // sessionStorage is browser-only - reading it during the initial render
    // (e.g. via a useState lazy initializer) would mismatch the server-
    // rendered markup. Deferring to an effect keeps first paint identical
    // on server and client, then syncs the real value right after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(sessionStorage.getItem(COLLAPSE_KEY) === "true");
    setGraduationDismissed(sessionStorage.getItem(GRADUATION_DISMISS_KEY) === "true");
  }, []);

  useEffect(() => {
    apiRequest<OnboardingChecklistResponse>("/api/v1/onboarding")
      .then((res) => setSteps(res.steps))
      .catch(() => setSteps([]));
  }, []);

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    sessionStorage.setItem(COLLAPSE_KEY, String(next));
  }

  async function requestHelp() {
    setHelpState("sending");
    try {
      await apiRequest("/api/v1/onboarding/help", { method: "POST", body: { note: null } });
      setHelpState("sent");
    } catch {
      setHelpState("idle");
    }
  }

  if (!steps || steps.length === 0) return null;
  const doneCount = steps.filter((s) => s.done).length;

  if (doneCount === steps.length) {
    if (graduationDismissed) return null;
    return (
      <div className="erp-panel flex items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="text-sm font-medium text-white">You&apos;ve mastered the basics.</p>
          <p className="mt-0.5 text-xs text-muted">
            BiznizFlowPilot covers 80% of your operations out of the box - MM Nexus builds the other 20%
            that&apos;s unique to your business.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <a
            href={MM_NEXUS_CONTACT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="whitespace-nowrap rounded-lg bg-tertiary-fixed-dim px-3 py-1.5 text-xs font-semibold text-black hover:opacity-90"
          >
            Talk to MM Nexus
          </a>
          <button
            type="button"
            onClick={() => {
              setGraduationDismissed(true);
              sessionStorage.setItem(GRADUATION_DISMISS_KEY, "true");
            }}
            aria-label="Dismiss"
            className="text-muted hover:text-white"
          >
            &times;
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="erp-panel">
      <div className="flex items-center justify-between gap-3 px-5 py-4">
        <div className="flex items-center gap-2">
          <AppTileIcon name="task_alt" className="h-4 w-4 text-tertiary-fixed-dim" />
          <h2 className="text-sm font-semibold text-[#aaa]">Getting Started</h2>
          <span className="rounded-full bg-[#1f1f1f] px-2 py-0.5 text-[10px] font-semibold text-muted">
            {doneCount}/{steps.length} done
          </span>
        </div>
        <button
          type="button"
          onClick={toggleCollapsed}
          className="text-xs font-medium text-muted hover:text-white"
        >
          {collapsed ? "Show" : "Hide"}
        </button>
      </div>

      {!collapsed && (
        <div className="border-t border-border px-5 py-4">
          <ul className="grid gap-2 sm:grid-cols-2">
            {steps.map((step) => {
              const info = ONBOARDING_STEPS[step.key];
              if (!info) return null;
              return (
                <li key={step.key}>
                  <Link
                    href={`/getting-started/${info.guideSlug}`}
                    className="flex items-start gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 transition-colors hover:bg-[#1f1f1f]"
                  >
                    <span
                      className={`mt-0.5 h-4 w-4 shrink-0 rounded-full border ${
                        step.done ? "border-emerald-500 bg-emerald-500" : "border-[#555]"
                      }`}
                    />
                    <span>
                      <span className={`block text-sm font-medium ${step.done ? "text-muted line-through" : "text-white"}`}>
                        {info.title}
                      </span>
                      <span className="block text-xs text-muted">{info.description}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex items-center gap-3 border-t border-border pt-3">
            {helpState === "sent" ? (
              <p className="text-xs text-emerald-400">Thanks - we&apos;ll be in touch to help you get set up.</p>
            ) : (
              <button
                type="button"
                onClick={() => void requestHelp()}
                disabled={helpState === "sending"}
                className="text-xs font-medium text-muted underline decoration-dotted hover:text-white disabled:opacity-50"
              >
                {helpState === "sending" ? "Sending…" : "Stuck? Get help"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
