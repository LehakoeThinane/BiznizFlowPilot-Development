"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { useRequireRole } from "@/hooks/useRequireRole";
import type { Organization, OrganizationDomain } from "@/types/api";

const INPUT =
  "w-full rounded-md border border-[#333] bg-[#0f0f0f] px-3 py-2 text-sm text-white outline-none placeholder:text-[#555] focus:ring-2 focus:ring-brand/50";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[#222] bg-[#141414] p-6">
      <h2 className="mb-5 text-base font-semibold text-white">{title}</h2>
      {children}
    </div>
  );
}

function Alert({ ok, text }: { ok: boolean; text: string }) {
  return (
    <p
      className={`rounded-md border px-3 py-2 text-sm ${
        ok
          ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-400"
          : "border-red-900/40 bg-red-950/30 text-red-400"
      }`}
    >
      {text}
    </p>
  );
}

export default function OrganizationPage() {
  const { allowed, checked } = useRequireRole(["it_admin"]);

  const [org, setOrg] = useState<Organization | null>(null);
  const [domains, setDomains] = useState<OrganizationDomain[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [newDomain, setNewDomain] = useState("");
  const [addingDomain, setAddingDomain] = useState(false);
  const [domainMsg, setDomainMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!allowed) return;
    void loadAll();
  }, [allowed]);

  async function loadAll() {
    setLoading(true);
    try {
      const [orgData, domainData] = await Promise.all([
        apiRequest<Organization>("/api/v1/org"),
        apiRequest<OrganizationDomain[]>("/api/v1/org/domains"),
      ]);
      setOrg(orgData);
      setName(orgData.name);
      setDomains(domainData);
    } catch {
      // handled inline via empty state below
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveName(e: FormEvent) {
    e.preventDefault();
    setSavingName(true);
    setNameMsg(null);
    try {
      const updated = await apiRequest<Organization>("/api/v1/org", {
        method: "PATCH",
        body: { name: name.trim() },
      });
      setOrg(updated);
      setNameMsg({ ok: true, text: "Organization name updated." });
    } catch (err) {
      setNameMsg({ ok: false, text: err instanceof Error ? err.message : "Update failed." });
    } finally {
      setSavingName(false);
    }
  }

  async function handleAddDomain(e: FormEvent) {
    e.preventDefault();
    setAddingDomain(true);
    setDomainMsg(null);
    try {
      const domain = await apiRequest<OrganizationDomain>("/api/v1/org/domains", {
        method: "POST",
        body: { domain: newDomain.trim().toLowerCase(), is_primary: domains.length === 0 },
      });
      setDomains((prev) => [...prev, domain]);
      setNewDomain("");
      setDomainMsg({ ok: true, text: "Domain added." });
    } catch (err) {
      setDomainMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to add domain." });
    } finally {
      setAddingDomain(false);
    }
  }

  async function handleRemoveDomain(id: string) {
    try {
      await apiRequest(`/api/v1/org/domains/${id}`, { method: "DELETE" });
      setDomains((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setDomainMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to remove domain." });
    }
  }

  if (!checked || !allowed) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Organization</h1>
          <p className="mt-1 text-sm text-[#888]">Manage your organization, domains, and subsidiaries</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/organization/subsidiaries"
            className="rounded-md border border-[#333] px-3 py-2 text-sm font-medium text-[#aaa] hover:border-[#555] hover:text-white"
          >
            Subsidiaries
          </Link>
          <Link
            href="/organization/invites"
            className="rounded-md border border-[#333] px-3 py-2 text-sm font-medium text-[#aaa] hover:border-[#555] hover:text-white"
          >
            Invites
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[#888]">Loading…</p>
      ) : (
        <>
          <Section title="Organization details">
            <form onSubmit={handleSaveName} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#aaa]" htmlFor="org-name">
                  Name
                </label>
                <input id="org-name" className={INPUT} value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="flex items-center gap-3 text-sm text-[#888]">
                <span className="rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-medium capitalize text-on-primary-container">
                  {org?.plan_tier}
                </span>
                <span>Subscription: {org?.subscription_status}</span>
              </div>
              {nameMsg && <Alert ok={nameMsg.ok} text={nameMsg.text} />}
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={savingName}
                  className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
                >
                  {savingName ? "Saving…" : "Save changes"}
                </button>
              </div>
            </form>
          </Section>

          <Section title="Authorized email domains">
            <p className="mb-4 text-sm text-[#888]">
              Employees can only be invited using an email on one of these domains. Leave empty to allow any
              email domain.
            </p>
            <div className="mb-4 space-y-2">
              {domains.length === 0 && <p className="text-sm text-[#555]">No domains configured yet.</p>}
              {domains.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between rounded-md border border-[#222] bg-[#0f0f0f] px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white">{d.domain}</span>
                    {d.is_primary && (
                      <span className="rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-medium text-on-primary-container">
                        Primary
                      </span>
                    )}
                    {!d.verified && <span className="text-[10px] text-[#666]">unverified</span>}
                  </div>
                  <button
                    onClick={() => handleRemoveDomain(d.id)}
                    className="text-xs text-rose-400 hover:text-rose-300"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <form onSubmit={handleAddDomain} className="flex gap-2">
              <input
                className={INPUT}
                placeholder="acmecorp.com"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                required
              />
              <button
                type="submit"
                disabled={addingDomain}
                className="shrink-0 rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              >
                {addingDomain ? "Adding…" : "Add"}
              </button>
            </form>
            {domainMsg && <div className="mt-3"><Alert ok={domainMsg.ok} text={domainMsg.text} /></div>}
          </Section>
        </>
      )}
    </div>
  );
}
