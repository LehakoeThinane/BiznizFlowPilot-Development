"use client";

import { FormEvent, useState } from "react";

import { apiRequest } from "@/lib/api";
import type { CheckoutResponse, PlanTier } from "@/types/api";

interface FeatureGroup {
  heading: string;
  items: string[];
}

interface PlanOption {
  tier: PlanTier;
  label: string;
  price: string;
  period: string;
  pitch: string;
  inherits?: string;
  groups: FeatureGroup[];
  featured?: boolean;
}

const PLANS: PlanOption[] = [
  {
    tier: "starter",
    label: "Starter",
    price: "$29",
    period: "/mo",
    pitch: "For one team getting the basics organized.",
    groups: [
      { heading: "Core", items: ["Up to 5 team members", "1 business location"] },
      { heading: "Operations", items: ["CRM: leads & customer records", "Task management & assignment", "Inventory for 1 location", "Simple invoicing"] },
      { heading: "Support", items: ["Email support"] },
    ],
  },
  {
    tier: "professional",
    label: "Professional",
    price: "$79",
    period: "/mo",
    pitch: "For growing teams that need automation.",
    inherits: "Everything in Starter, plus:",
    featured: true,
    groups: [
      { heading: "Core", items: ["Up to 25 team members"] },
      { heading: "Operations", items: ["Multiple inventory locations + low-stock alerts", "Sales orders & purchase orders", "Expense tracking & profit/loss reporting"] },
      { heading: "Collaboration", items: ["Unlimited workflow automations", "Video & voice meetings", "Team messaging"] },
      { heading: "Support", items: ["Priority support"] },
    ],
  },
  {
    tier: "enterprise",
    label: "Enterprise",
    price: "Custom",
    period: "",
    pitch: "For multi-location or multi-brand businesses.",
    inherits: "Everything in Professional, plus:",
    groups: [
      { heading: "Core", items: ["Unlimited team members", "Multiple subsidiary businesses, one account"] },
      { heading: "Operations", items: ["HR: departments, leave, payroll, org chart", "Org-wide admin role across every subsidiary"] },
      { heading: "Support", items: ["Dedicated onboarding", "Custom contract terms"] },
    ],
  },
];

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      className="mt-0.5 h-4 w-4 flex-shrink-0 text-tertiary-fixed-dim"
    >
      <path
        d="M16.5 5.5 8 14l-4.5-4.5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function PricingPage() {
  const [selectedTier, setSelectedTier] = useState<PlanTier>("professional");
  const [orgName, setOrgName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedPlan = PLANS.find((p) => p.tier === selectedTier) ?? PLANS[0];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedOrgName = orgName.trim();
    const trimmedEmail = ownerEmail.trim();
    if (!trimmedOrgName || !trimmedEmail) {
      setError("Please fill in your company name and email.");
      return;
    }

    setIsSubmitting(true);
    try {
      const { checkout_url } = await apiRequest<CheckoutResponse>("/api/v1/billing/checkout", {
        method: "POST",
        body: { org_name: trimmedOrgName, owner_email: trimmedEmail, plan_tier: selectedTier },
      });
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout. Please try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen px-4 pb-24 pt-20 sm:px-8">
      <div className="mx-auto max-w-6xl">
        {/* ── Hero ── */}
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-label-caps text-brand">Pricing</p>
          <h1 className="text-display mt-3 text-balance text-[2.5rem] sm:text-[3rem]">
            One operations platform, priced for how you actually run the business
          </h1>
          <p className="text-body-base mt-4 text-muted">
            Every plan gets a real invite for your first owner account within minutes of payment —
            no sales call required to get started.
          </p>
        </div>

        {/* ── Tier grid ── */}
        <div className="mt-16 grid gap-6 lg:grid-cols-3">
          {PLANS.map((plan) => {
            const isSelected = plan.tier === selectedTier;
            return (
              <div
                key={plan.tier}
                className={`relative flex flex-col rounded-2xl border p-6 transition-colors ${
                  plan.featured
                    ? "border-tertiary-fixed-dim/50 bg-surface shadow-[0_0_0_1px_rgba(45,212,191,0.12),0_20px_60px_rgba(2,8,20,0.45)]"
                    : "border-border bg-surface-dim"
                } ${isSelected ? "outline outline-2 outline-offset-2 outline-brand/60" : ""}`}
              >
                {plan.featured ? (
                  <span className="text-label-caps absolute -top-3 left-6 rounded-full bg-tertiary-fixed-dim px-3 py-1 text-tertiary">
                    Most popular
                  </span>
                ) : null}

                <h2 className="text-h2">{plan.label}</h2>
                <p className="text-body-sm mt-1 text-muted">{plan.pitch}</p>

                <div className="mt-5 flex items-baseline gap-1 [font-variant-numeric:tabular-nums]">
                  <span className="text-display text-[2.25rem]">{plan.price}</span>
                  {plan.period ? <span className="text-body-base text-muted">{plan.period}</span> : null}
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedTier(plan.tier)}
                  className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors ${
                    isSelected
                      ? "erp-button-primary"
                      : "border border-border bg-surface text-on-surface hover:bg-[#1f1f1f]"
                  }`}
                >
                  {isSelected ? "Selected" : `Choose ${plan.label}`}
                </button>

                <div className="mt-7 flex flex-col gap-5">
                  {plan.inherits ? (
                    <p className="text-body-sm font-medium text-on-surface-variant">{plan.inherits}</p>
                  ) : null}
                  {plan.groups.map((group) => (
                    <div key={group.heading}>
                      <p className="text-label-caps text-on-surface-variant">{group.heading}</p>
                      <ul className="mt-2.5 flex flex-col gap-2">
                        {group.items.map((item) => (
                          <li key={item} className="text-body-sm flex items-start gap-2">
                            <CheckIcon />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Signup ── */}
        <section className="erp-panel mx-auto mt-16 w-full max-w-md p-6">
          <h3 className="text-h3">
            Subscribe to <span className="text-brand">{selectedPlan.label}</span>
          </h3>
          <p className="text-body-sm mt-1 text-muted">
            {selectedPlan.price}
            {selectedPlan.period} · billed to your company
          </p>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit} noValidate>
            <div>
              <label className="text-label-semibold mb-1.5 block" htmlFor="org-name">
                Company name
              </label>
              <input
                id="org-name"
                type="text"
                required
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
                className="erp-input w-full px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="text-label-semibold mb-1.5 block" htmlFor="owner-email">
                Your work email
              </label>
              <input
                id="owner-email"
                type="email"
                required
                value={ownerEmail}
                onChange={(event) => setOwnerEmail(event.target.value)}
                className="erp-input w-full px-3 py-2 text-sm"
              />
              <p className="text-body-sm mt-1.5 text-on-surface-variant">
                We&apos;ll send your team&apos;s invite link here after payment. Teammates can only
                be invited from this same email domain.
              </p>
            </div>

            {error ? (
              <p className="text-body-sm rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-red-400">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold transition-opacity disabled:opacity-60"
            >
              {isSubmitting ? "Redirecting to payment…" : `Continue to payment`}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
