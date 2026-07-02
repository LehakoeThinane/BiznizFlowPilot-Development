"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { useRequireRole } from "@/hooks/useRequireRole";
import type { Subsidiary, SubsidiaryListResponse } from "@/types/api";

const INPUT =
  "w-full rounded-md border border-[#333] bg-[#0f0f0f] px-3 py-2 text-sm text-white outline-none placeholder:text-[#555] focus:ring-2 focus:ring-brand/50";

export default function SubsidiariesPage() {
  const { allowed, checked } = useRequireRole(["it_admin"]);

  const [subsidiaries, setSubsidiaries] = useState<Subsidiary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    void load();
  }, [allowed]);

  async function load() {
    setLoading(true);
    try {
      const res = await apiRequest<SubsidiaryListResponse>("/api/v1/org/subsidiaries");
      setSubsidiaries(res.items);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const created = await apiRequest<Subsidiary>("/api/v1/org/subsidiaries", {
        method: "POST",
        body: { name: name.trim(), email: email.trim(), phone: phone.trim() || undefined },
      });
      setSubsidiaries((prev) => [...prev, created]);
      setName("");
      setEmail("");
      setPhone("");
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create subsidiary.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeactivate(id: string) {
    if (!confirm("Deactivate this subsidiary? It will be hidden but not deleted.")) return;
    try {
      await apiRequest(`/api/v1/org/subsidiaries/${id}`, { method: "DELETE" });
      setSubsidiaries((prev) => prev.map((s) => (s.id === id ? { ...s, is_active: false } : s)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate subsidiary.");
    }
  }

  if (!checked || !allowed) return null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/organization" className="text-xs text-[#666] hover:text-[#aaa]">
            ← Organization
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-white">Subsidiaries</h1>
          <p className="mt-1 text-sm text-[#888]">Each subsidiary has fully separate data, inventory, and books.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
        >
          {showForm ? "Cancel" : "New subsidiary"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="space-y-4 rounded-xl border border-[#222] bg-[#141414] p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#aaa]">Name</label>
              <input className={INPUT} required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#aaa]">Contact email</label>
              <input
                type="email"
                className={INPUT}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[#aaa]">Phone (optional)</label>
            <input className={INPUT} value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          {error && (
            <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={creating}
              className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
            >
              {creating ? "Creating…" : "Create subsidiary"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-[#888]">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[#222]">
          <table className="w-full text-sm">
            <thead className="bg-[#141414] text-left text-xs uppercase text-[#666]">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Users</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {subsidiaries.map((s) => (
                <tr key={s.id} className="border-t border-[#222]">
                  <td className="px-4 py-3 text-white">
                    {s.name}
                    {s.is_primary_subsidiary && (
                      <span className="ml-2 rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-medium text-on-primary-container">
                        Primary
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#aaa]">{s.email}</td>
                  <td className="px-4 py-3 text-[#aaa]">{s.user_count}</td>
                  <td className="px-4 py-3">
                    <span className={s.is_active ? "text-emerald-400" : "text-[#666]"}>
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!s.is_primary_subsidiary && s.is_active && (
                      <button
                        onClick={() => handleDeactivate(s.id)}
                        className="text-xs text-rose-400 hover:text-rose-300"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
