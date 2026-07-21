"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

import { signupTrial, signupTrialWithGoogle } from "@/lib/auth";

const INPUT = "erp-input w-full px-3 py-2 text-sm";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

interface FormState {
  organizationName: string;
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const EMPTY: FormState = {
  organizationName: "",
  firstName: "",
  lastName: "",
  email: "",
  password: "",
  confirmPassword: "",
};

export default function SignupPage() {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);

  function set(field: keyof FormState, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsSubmitting(true);
    try {
      await signupTrial({
        organization_name: form.organizationName,
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        password: form.password,
      });
      window.location.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleSuccess(credential: string) {
    setError(null);
    if (!form.organizationName.trim()) {
      setError("Enter your business name above first, then continue with Google.");
      return;
    }
    setGoogleBusy(true);
    try {
      await signupTrialWithGoogle({ organization_name: form.organizationName, credential });
      window.location.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setGoogleBusy(false);
    }
  }

  const Logo = (
    <div className="mb-6 flex items-center gap-3">
      <div className="glow-badge flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-lg font-bold text-on-primary">B</div>
      <div>
        <h1 className="text-xl font-semibold text-foreground">BiznizFlowPilot</h1>
        <p className="text-xs text-muted">Start your free 14-day trial - no credit card required.</p>
      </div>
    </div>
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-sm">
        {Logo}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="organizationName">
              Business name
            </label>
            <input
              id="organizationName"
              type="text"
              required
              value={form.organizationName}
              onChange={(e) => set("organizationName", e.target.value)}
              className={INPUT}
              placeholder="Your business name"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="firstName">
                First name
              </label>
              <input
                id="firstName"
                type="text"
                required
                value={form.firstName}
                onChange={(e) => set("firstName", e.target.value)}
                className={INPUT}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="lastName">
                Last name
              </label>
              <input
                id="lastName"
                type="text"
                required
                value={form.lastName}
                onChange={(e) => set("lastName", e.target.value)}
                className={INPUT}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              className={INPUT}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              className={INPUT}
              placeholder="At least 8 characters"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="confirmPassword">
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              value={form.confirmPassword}
              onChange={(e) => set("confirmPassword", e.target.value)}
              className={INPUT}
            />
          </div>

          {error && (
            <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="erp-button-primary w-full px-3 py-2.5 text-sm font-semibold disabled:opacity-60"
          >
            {isSubmitting ? "Creating your trial..." : "Start free trial"}
          </button>
        </form>

        {GOOGLE_CLIENT_ID && (
          <>
            <div className="my-4 flex items-center gap-3">
              <div className="h-px flex-1 bg-border" />
              <span className="text-xs text-muted">or</span>
              <div className="h-px flex-1 bg-border" />
            </div>

            <div className="flex justify-center">
              <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                <GoogleLogin
                  onSuccess={(response) => {
                    if (response.credential) void handleGoogleSuccess(response.credential);
                  }}
                  onError={() => setError("Google sign-in failed")}
                  text="continue_with"
                  width="336"
                />
              </GoogleOAuthProvider>
            </div>
            {googleBusy && <p className="mt-2 text-center text-xs text-muted">Setting up your trial...</p>}
          </>
        )}

        <p className="mt-6 text-center text-xs text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
