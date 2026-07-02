"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { OrganizationAdminListResponse, OrganizationProvisionRequest } from "@/types/api";

const INPUT = "w-full rounded-md border border-[#2a2a3a] bg-[#151520] px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

const EMPTY_FORM: OrganizationProvisionRequest = {
  org_name: "",
  billing_email: "",
  owner_email: "",
  owner_password: "",
  owner_first_name: "",
  owner_last_name: "",
  plan_tier: "trial",
};

export default function PlatformOrganizationsPage() {
  const [data, setData] = useState<OrganizationAdminListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<OrganizationProvisionRequest>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function load() {
    platformApiRequest<OrganizationAdminListResponse>("/platform/v1/organizations")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load organizations"));
  }

  useEffect(load, []);

  async function handleProvision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await platformApiRequest("/platform/v1/organizations", { method: "POST", body: form });
      setShowForm(false);
      setForm(EMPTY_FORM);
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to provision organization");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Organizations</h1>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-semibold text-white"
        >
          {showForm ? "Cancel" : "Provision new client"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleProvision}
          className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-[#22222e] bg-[#12121a] p-4 sm:grid-cols-2"
        >
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Organization name</label>
            <input
              required
              className={INPUT}
              value={form.org_name}
              onChange={(e) => setForm({ ...form, org_name: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Billing email</label>
            <input
              required
              type="email"
              className={INPUT}
              value={form.billing_email}
              onChange={(e) => setForm({ ...form, billing_email: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Plan tier</label>
            <select
              className={INPUT}
              value={form.plan_tier}
              onChange={(e) => setForm({ ...form, plan_tier: e.target.value })}
            >
              <option value="trial">Trial</option>
              <option value="starter">Starter</option>
              <option value="professional">Professional</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Owner first name</label>
            <input
              required
              className={INPUT}
              value={form.owner_first_name}
              onChange={(e) => setForm({ ...form, owner_first_name: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Owner last name</label>
            <input
              required
              className={INPUT}
              value={form.owner_last_name}
              onChange={(e) => setForm({ ...form, owner_last_name: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Owner email</label>
            <input
              required
              type="email"
              className={INPUT}
              value={form.owner_email}
              onChange={(e) => setForm({ ...form, owner_email: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Owner temporary password</label>
            <input
              required
              type="password"
              minLength={8}
              className={INPUT}
              value={form.owner_password}
              onChange={(e) => setForm({ ...form, owner_password: e.target.value })}
            />
          </div>

          {formError && (
            <p className="sm:col-span-2 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
              {formError}
            </p>
          )}

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {isSubmitting ? "Provisioning..." : "Provision organization"}
            </button>
          </div>
        </form>
      )}

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
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Subsidiaries</th>
              <th className="px-4 py-3">Users</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((org) => (
              <tr key={org.id} className="border-t border-[#1c1c26] hover:bg-white/[0.02]">
                <td className="px-4 py-3">
                  <Link href={`/platform/organizations/${org.id}`} className="text-violet-300 hover:underline">
                    {org.name}
                  </Link>
                  <p className="text-xs text-[#666]">{org.billing_email}</p>
                </td>
                <td className="px-4 py-3 capitalize text-[#ccc]">{org.plan_tier}</td>
                <td className="px-4 py-3 capitalize text-[#ccc]">{org.subscription_status}</td>
                <td className="px-4 py-3 text-[#ccc]">{org.subsidiary_count}</td>
                <td className="px-4 py-3 text-[#ccc]">{org.user_count}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-[#666]">
                  No organizations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
