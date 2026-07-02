"use client";

import { Suspense, FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiRequest } from "@/lib/api";
import { acceptInvite } from "@/lib/auth";
import type { InvitationValidateResponse } from "@/types/api";

function AcceptInviteForm() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [invite, setInvite] = useState<InvitationValidateResponse | null>(null);
  const [validating, setValidating] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setValidationError("This invitation link is missing a token.");
      setValidating(false);
      return;
    }
    apiRequest<InvitationValidateResponse>("/api/v1/auth/invite/validate", {
      method: "GET",
      query: { token },
    })
      .then((res) => setInvite(res))
      .catch((err) =>
        setValidationError(err instanceof Error ? err.message : "This invitation is invalid or has expired."),
      )
      .finally(() => setValidating(false));
  }, [token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    if (password.length < 8) {
      setSubmitError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setSubmitError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await acceptInvite({
        token,
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      window.location.replace("/home");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to accept invitation.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4 py-8">
      <section className="w-full max-w-md rounded-xl border border-[#222] bg-[#141414] p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-lg font-bold text-white">
            B
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">BiznizFlowPilot</h1>
            <p className="text-xs text-[#666]">Accept your invitation</p>
          </div>
        </div>

        {validating ? (
          <p className="text-sm text-[#888]">Checking your invitation…</p>
        ) : validationError ? (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
            {validationError}
          </p>
        ) : invite ? (
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            <p className="rounded-md border border-[#222] bg-[#0f0f0f] px-3 py-2 text-sm text-[#aaa]">
              You&apos;ve been invited to join <span className="text-white">{invite.business_name}</span> (
              {invite.organization_name}) as <span className="capitalize text-white">{invite.role}</span>,
              using <span className="text-white">{invite.masked_email}</span>.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="first-name">
                  First name
                </label>
                <input
                  id="first-name"
                  type="text"
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="erp-input w-full px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="last-name">
                  Last name
                </label>
                <input
                  id="last-name"
                  type="text"
                  required
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="erp-input w-full px-3 py-2 text-sm"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="erp-input w-full px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-[#555]">Use at least 8 characters.</p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="confirm-password">
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="erp-input w-full px-3 py-2 text-sm"
              />
            </div>

            {submitError && (
              <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
                {submitError}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md bg-brand px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
            >
              {submitting ? "Creating account…" : "Accept & create account"}
            </button>
          </form>
        ) : null}
      </section>
    </main>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={null}>
      <AcceptInviteForm />
    </Suspense>
  );
}
