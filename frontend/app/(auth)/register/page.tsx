"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { getCurrentUser, getStoredToken, register } from "@/lib/auth";


export default function RegisterPage() {
  const [businessName, setBusinessName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!getStoredToken()) return;
    void getCurrentUser()
      .then(() => window.location.replace("/dashboard"))
      .catch(() => {});
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedBusinessName = businessName.trim();
    const trimmedFirstName = firstName.trim();
    const trimmedLastName = lastName.trim();
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!trimmedBusinessName || !trimmedFirstName || !trimmedLastName || !trimmedEmail || !trimmedPassword) {
      setError("All fields are required.");
      return;
    }

    if (trimmedPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (trimmedPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await register({
        business_name: trimmedBusinessName,
        first_name: trimmedFirstName,
        last_name: trimmedLastName,
        email: trimmedEmail,
        password: trimmedPassword,
      });
      window.location.replace("/dashboard");
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "Registration failed";
      setError(
        message === "Request failed"
          ? "We could not create your account. Check the details and try again."
          : message,
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4 py-8">
      <section className="w-full max-w-md rounded-xl border border-[#222] bg-[#141414] p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-lg font-bold text-white">B</div>
          <div>
            <h1 className="text-xl font-semibold text-white">BiznizFlowPilot</h1>
            <p className="text-xs text-[#666]">Create your first business account.</p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <div>
            <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="business-name">
              Business name
            </label>
            <input
              id="business-name"
              type="text"
              required
              value={businessName}
              onChange={(event) => setBusinessName(event.target.value)}
              className="erp-input w-full px-3 py-2 text-sm"
            />
          </div>

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
                onChange={(event) => setFirstName(event.target.value)}
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
                onChange={(event) => setLastName(event.target.value)}
                className="erp-input w-full px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="erp-input w-full px-3 py-2 text-sm"
            />
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
              onChange={(event) => setPassword(event.target.value)}
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
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="erp-input w-full px-3 py-2 text-sm"
            />
          </div>

          {error ? (
            <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{error}</p>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-brand px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
          >
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>

          <p className="text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
