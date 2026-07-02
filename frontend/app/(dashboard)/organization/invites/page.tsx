"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { useRequireRole } from "@/hooks/useRequireRole";
import type { InvitationListResponse, UserInvitation, UserRole } from "@/types/api";

const INPUT =
  "w-full rounded-md border border-[#333] bg-[#0f0f0f] px-3 py-2 text-sm text-white outline-none placeholder:text-[#555] focus:ring-2 focus:ring-brand/50";

const ROLE_OPTIONS: UserRole[] = ["staff", "manager", "owner", "it_admin"];

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-950/40 text-amber-400",
    accepted: "bg-emerald-950/40 text-emerald-400",
    revoked: "bg-[#222] text-[#888]",
    expired: "bg-[#222] text-[#888]",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${styles[status] ?? ""}`}>
      {status}
    </span>
  );
}

export default function InvitesPage() {
  const { allowed, checked } = useRequireRole(["it_admin"]);

  const [invites, setInvites] = useState<UserInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("staff");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!allowed) return;
    void load();
  }, [allowed]);

  async function load() {
    setLoading(true);
    try {
      const res = await apiRequest<InvitationListResponse>("/api/v1/users/invites");
      setInvites(res.items);
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    setSending(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await apiRequest<UserInvitation>("/api/v1/users/invite", {
        method: "POST",
        body: { email: email.trim(), role },
      });
      setInvites((prev) => [created, ...prev]);
      setEmail("");
      setSuccess(`Invitation sent to ${created.email}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send invitation.");
    } finally {
      setSending(false);
    }
  }

  async function handleRevoke(id: string) {
    try {
      await apiRequest(`/api/v1/users/invites/${id}`, { method: "DELETE" });
      setInvites((prev) => prev.map((i) => (i.id === id ? { ...i, status: "revoked" } : i)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke invitation.");
    }
  }

  if (!checked || !allowed) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link href="/organization" className="text-xs text-[#666] hover:text-[#aaa]">
          ← Organization
        </Link>
        <h1 className="mt-1 text-2xl font-semibold text-white">Invitations</h1>
        <p className="mt-1 text-sm text-[#888]">
          Invite employees across every subsidiary in your organization. If you&apos;ve set authorized email
          domains, only matching addresses can be invited.
        </p>
      </div>

      <form onSubmit={handleInvite} className="space-y-4 rounded-xl border border-[#222] bg-[#141414] p-6">
        <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[#aaa]">Email</label>
            <input
              type="email"
              required
              className={INPUT}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="person@company.com"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[#aaa]">Role</label>
            <select className={INPUT} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}
        {success && (
          <p className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-400">
            {success}
          </p>
        )}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={sending}
            className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
          >
            {sending ? "Sending…" : "Send invitation"}
          </button>
        </div>
      </form>

      {loading ? (
        <p className="text-sm text-[#888]">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[#222]">
          <table className="w-full text-sm">
            <thead className="bg-[#141414] text-left text-xs uppercase text-[#666]">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {invites.map((i) => (
                <tr key={i.id} className="border-t border-[#222]">
                  <td className="px-4 py-3 text-white">{i.email}</td>
                  <td className="px-4 py-3 capitalize text-[#aaa]">{i.role}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={i.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {i.status === "pending" && (
                      <button
                        onClick={() => handleRevoke(i.id)}
                        className="text-xs text-rose-400 hover:text-rose-300"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {invites.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-[#555]">
                    No invitations sent yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
