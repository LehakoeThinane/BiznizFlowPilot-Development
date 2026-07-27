"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { OrganizationAdmin, OrganizationAdminUpdate } from "@/types/api";

const INPUT = "w-full rounded-md border border-[#2a2a3a] bg-[#151520] px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

export default function PlatformOrganizationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [org, setOrg] = useState<OrganizationAdmin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [name, setName] = useState("");
  const [planTier, setPlanTier] = useState("trial");
  const [subscriptionStatus, setSubscriptionStatus] = useState("active");
  const [seatsIncluded, setSeatsIncluded] = useState<string>("");

  function load() {
    platformApiRequest<OrganizationAdmin>(`/platform/v1/organizations/${params.id}`)
      .then((data) => {
        setOrg(data);
        setName(data.name);
        setPlanTier(data.plan_tier);
        setSubscriptionStatus(data.subscription_status);
        setSeatsIncluded(data.seats_included?.toString() ?? "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load organization"));
  }

  useEffect(load, [params.id]);

  async function handleSave() {
    setSaveError(null);
    setIsSaving(true);
    const body: OrganizationAdminUpdate = {
      name,
      plan_tier: planTier,
      subscription_status: subscriptionStatus,
      seats_included: seatsIncluded ? Number(seatsIncluded) : undefined,
    };
    try {
      const updated = await platformApiRequest<OrganizationAdmin>(
        `/platform/v1/organizations/${params.id}`,
        { method: "PATCH", body },
      );
      setOrg(updated);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setIsSaving(false);
    }
  }

  if (error) {
    return <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{error}</p>;
  }
  if (!org) {
    return <p className="text-sm text-[#777]">Loading…</p>;
  }

  return (
    <div className="max-w-2xl">
      <button
        type="button"
        onClick={() => router.push("/platform/organizations")}
        className="mb-4 text-xs text-[#777] hover:text-white"
      >
        ← Back to organizations
      </button>

      <h1 className="mb-1 text-lg font-semibold text-white">{org.name}</h1>
      <p className="mb-6 text-sm text-[#777]">
        {org.subsidiary_count} subsidiar{org.subsidiary_count === 1 ? "y" : "ies"} · {org.user_count} users
        {" · "}
        <Link href={`/platform/organizations/${params.id}/email-config`} className="text-violet-400 hover:underline">
          Custom email sender →
        </Link>
      </p>

      <div className="space-y-4 rounded-xl border border-[#22222e] bg-[#12121a] p-5">
        <div>
          <label className="mb-1 block text-xs font-medium text-[#aaa]">Name</label>
          <input className={INPUT} value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Plan tier</label>
            <select className={INPUT} value={planTier} onChange={(e) => setPlanTier(e.target.value)}>
              <option value="trial">Trial</option>
              <option value="starter">Starter</option>
              <option value="growth">Growth</option>
              <option value="professional">Professional</option>
              <option value="enterprise">Enterprise</option>
              <option value="legacy">Legacy</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Subscription status</label>
            <select
              className={INPUT}
              value={subscriptionStatus}
              onChange={(e) => setSubscriptionStatus(e.target.value)}
            >
              <option value="trial">Trial</option>
              <option value="active">Active</option>
              <option value="past_due">Past due</option>
              <option value="suspended">Suspended</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[#aaa]">Seats included</label>
          <input
            type="number"
            min={0}
            className={INPUT}
            value={seatsIncluded}
            onChange={(e) => setSeatsIncluded(e.target.value)}
            placeholder="Unlimited"
          />
        </div>

        {saveError && (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
            {saveError}
          </p>
        )}

        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          {isSaving ? "Saving..." : "Save changes"}
        </button>
      </div>
    </div>
  );
}
