"use client";

import { FormEvent, useState } from "react";

import { apiRequest } from "@/lib/api";
import type { CheckoutResponse, PlanTier } from "@/types/api";

interface PlanOption {
  tier: PlanTier;
  label: string;
  price: string;
  blurb: string;
}

const PLANS: PlanOption[] = [
  { tier: "starter", label: "Starter", price: "$29/mo", blurb: "For small teams getting started." },
  { tier: "professional", label: "Professional", price: "$79/mo", blurb: "For growing operations teams." },
  { tier: "enterprise", label: "Enterprise", price: "Contact us", blurb: "For larger, multi-location businesses." },
];

export default function PricingPage() {
  const [selectedTier, setSelectedTier] = useState<PlanTier>("starter");
  const [orgName, setOrgName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
        body: {
          org_name: trimmedOrgName,
          owner_email: trimmedEmail,
          plan_tier: selectedTier,
        },
      });
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout. Please try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0a] px-4 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-10 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-2xl font-bold text-white">
            B
          </div>
          <h1 className="text-3xl font-semibold text-white">Plans for every operations team</h1>
          <p className="mt-2 text-sm text-[#888]">
            Pick a plan, enter your company details, and your team gets an invite by email once payment completes.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-3">
          {PLANS.map((plan) => (
            <button
              key={plan.tier}
              type="button"
              onClick={() => setSelectedTier(plan.tier)}
              className={`rounded-xl border p-6 text-left transition-colors ${
                selectedTier === plan.tier
                  ? "border-emerald-600 bg-[#141414]"
                  : "border-[#222] bg-[#101010] hover:border-[#333]"
              }`}
            >
              <h2 className="text-lg font-semibold text-white">{plan.label}</h2>
              <p className="mt-1 text-2xl font-bold text-emerald-500">{plan.price}</p>
              <p className="mt-2 text-sm text-[#888]">{plan.blurb}</p>
            </button>
          ))}
        </div>

        <section className="mx-auto mt-12 w-full max-w-md rounded-xl border border-[#222] bg-[#141414] p-6 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold text-white">
            Subscribe to {PLANS.find((p) => p.tier === selectedTier)?.label}
          </h3>
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="org-name">
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
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="owner-email">
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
              <p className="mt-1 text-xs text-[#555]">
                We&apos;ll send your team&apos;s invite link here after payment. Your teammates&apos; invites will
                only work with this same email domain.
              </p>
            </div>

            {error ? (
              <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-brand px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
            >
              {isSubmitting ? "Redirecting to payment…" : "Continue to payment"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
