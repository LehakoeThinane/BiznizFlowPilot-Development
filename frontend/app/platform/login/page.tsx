"use client";

import { FormEvent, useEffect, useState } from "react";

import { getCurrentPlatformAdmin, platformLogin } from "@/lib/platform-auth";
import { getPlatformAccessToken } from "@/lib/platform-api";

const INPUT = "w-full rounded-md border border-[#2a2a3a] bg-[#151520] px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

export default function PlatformLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!getPlatformAccessToken()) return;
    void getCurrentPlatformAdmin()
      .then(() => window.location.replace("/platform"))
      .catch(() => {});
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await platformLogin({ email, password });
      window.location.replace("/platform");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <section className="w-full max-w-md rounded-xl border border-[#2a2a3a] bg-[#12121a] p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-lg font-bold text-white">
            P
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">Platform Console</h1>
            <p className="text-xs text-[#777]">Vendor staff sign-in — not for client accounts.</p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={INPUT}
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={INPUT}
            />
          </div>

          {error && (
            <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-violet-600 px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
