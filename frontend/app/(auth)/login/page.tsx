"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { getCurrentUser, getStoredToken, login } from "@/lib/auth";

type Mode = "login" | "reset-request" | "reset-confirm";

const INPUT = "erp-input w-full px-3 py-2 text-sm";

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");

  // Login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset step 1
  const [resetEmail, setResetEmail] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetLoading, setResetLoading] = useState(false);

  // Reset step 2
  const [confirmToken, setConfirmToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmSuccess, setConfirmSuccess] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);

  useEffect(() => {
    // If the user arrived via a password-reset email link (?reset_token=...),
    // switch straight to the confirm step and pre-fill the token.
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("reset_token");
    if (urlToken) {
      setConfirmToken(urlToken);
      setMode("reset-confirm");
      return;
    }

    // Only auto-redirect if bfp_session cookie is present — i.e. the user has
    // an active session. After logout(), bfp_session is synchronously cleared,
    // so this guard prevents the redirect loop where a still-valid bfp_access
    // cookie would otherwise keep bouncing the user back to the dashboard.
    if (!getStoredToken()) return;
    void getCurrentUser()
      .then(() => window.location.replace("/home"))
      .catch(() => {});
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
      window.location.replace("/home");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(
        message === "Invalid email or password"
          ? "We could not sign you in. Check your email and password, or contact your administrator if you haven't received an invite yet."
          : message,
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResetRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResetError(null);
    setResetLoading(true);
    try {
      await apiRequest<{ message: string }>(
        "/api/v1/auth/password-reset/request",
        { method: "POST", body: { email: resetEmail } }
      );
      // Token is sent to the user's email — advance to confirm step.
      setMode("reset-confirm");
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setResetLoading(false);
    }
  }

  async function handleResetConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConfirmError(null);
    if (newPassword !== confirmPassword) {
      setConfirmError("Passwords do not match");
      return;
    }
    if (newPassword.length < 8) {
      setConfirmError("Password must be at least 8 characters");
      return;
    }
    setConfirmLoading(true);
    try {
      await apiRequest("/api/v1/auth/password-reset/confirm", {
        method: "POST",
        body: { token: confirmToken, new_password: newPassword },
      });
      setConfirmSuccess(true);
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setConfirmLoading(false);
    }
  }

  const Logo = (
    <div className="mb-6 flex items-center gap-3">
      <div className="glow-badge flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-lg font-bold text-on-primary">B</div>
      <div>
        <h1 className="text-xl font-semibold text-foreground">BiznizFlowPilot</h1>
        <p className="text-xs text-muted">Sign in to the operational dashboard.</p>
      </div>
    </div>
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <section className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-sm">
        {Logo}

        {/* ── Login ── */}
        {mode === "login" && (
          <>
            <p className="mb-6 text-xs text-muted">
              Invited by your company? Use the invite link sent to your work email. Otherwise,{" "}
              <Link href="/signup" className="text-brand hover:underline">start a free trial</Link>.
            </p>
            <form className="space-y-4" onSubmit={handleLogin}>
              <div>
                <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="email">Email</label>
                <input id="email" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} className={INPUT} />
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-sm font-medium text-on-surface-variant" htmlFor="password">Password</label>
                  <button type="button" onClick={() => { setMode("reset-request"); setResetEmail(email); setResetError(null); }}
                    className="text-xs text-brand hover:underline">
                    Forgot password?
                  </button>
                </div>
                <input id="password" type="password" required value={password}
                  onChange={(e) => setPassword(e.target.value)} className={INPUT} />
              </div>

              {error && (
                <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{error}</p>
              )}

              <button type="submit" disabled={isSubmitting}
                className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold disabled:opacity-60">
                {isSubmitting ? "Signing in..." : "Sign in"}
              </button>
            </form>
          </>
        )}

        {/* ── Reset step 1: request token ── */}
        {mode === "reset-request" && (
          <>
            <p className="mb-1 text-sm font-semibold text-white">Reset your password</p>
            <p className="mb-5 text-xs text-muted">Enter your email and we'll send a reset link to your inbox.</p>
            <form className="space-y-4" onSubmit={handleResetRequest}>
              <div>
                <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="reset-email">Email</label>
                <input id="reset-email" type="email" required value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)} className={INPUT} />
              </div>

              {resetError && (
                <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{resetError}</p>
              )}

              <button type="submit" disabled={resetLoading}
                className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold disabled:opacity-60">
                {resetLoading ? "Sending..." : "Send reset link"}
              </button>

              <button type="button" onClick={() => setMode("login")}
                className="w-full text-center text-sm text-muted hover:text-on-surface-variant">
                ← Back to sign in
              </button>
            </form>
          </>
        )}

        {/* ── Reset step 2: enter token from email + new password ── */}
        {mode === "reset-confirm" && (
          <>
            <p className="mb-1 text-sm font-semibold text-white">Set a new password</p>
            {confirmSuccess ? (
              <div className="mt-4 space-y-4">
                <p className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-3 py-3 text-sm text-emerald-400">
                  Password reset successfully. You can now sign in.
                </p>
                <button type="button" onClick={() => { setMode("login"); setPassword(""); setError(null); }}
                  className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold">
                  Back to sign in
                </button>
              </div>
            ) : (
              <>
                <p className="mb-5 text-xs text-muted">Check your inbox for the reset link. Paste the token below.</p>
                <form className="space-y-4" onSubmit={handleResetConfirm}>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="confirm-token">Reset token</label>
                    <input id="confirm-token" type="text" required value={confirmToken}
                      onChange={(e) => setConfirmToken(e.target.value)}
                      className={`${INPUT} font-mono text-xs`} placeholder="Paste token from your email" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="new-password">New password</label>
                    <input id="new-password" type="password" required minLength={8} value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)} className={INPUT} placeholder="At least 8 characters" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="confirm-password">Confirm password</label>
                    <input id="confirm-password" type="password" required value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)} className={INPUT} />
                  </div>

                  {confirmError && (
                    <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{confirmError}</p>
                  )}

                  <button type="submit" disabled={confirmLoading}
                    className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold disabled:opacity-60">
                    {confirmLoading ? "Resetting..." : "Reset password"}
                  </button>

                  <button type="button" onClick={() => setMode("login")}
                    className="w-full text-center text-sm text-muted hover:text-on-surface-variant">
                    ← Back to sign in
                  </button>
                </form>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}
