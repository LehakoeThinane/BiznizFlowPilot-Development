"use client";

import { FormEvent, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";

const INPUT = "w-full rounded-md border border-[#2a2a3a] bg-[#151520] px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

export default function PlatformSettingsPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }

    setIsSubmitting(true);
    try {
      await platformApiRequest("/platform/v1/admins/me/change-password", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      setSuccess("Password changed successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div>
      <h1 className="mb-6 text-lg font-semibold text-white">Settings</h1>

      <div className="max-w-md rounded-xl border border-[#22222e] bg-[#12121a] p-6">
        <h2 className="mb-4 text-sm font-semibold text-white">Change password</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Current password</label>
            <input
              required
              type="password"
              className={INPUT}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">New password</label>
            <input
              required
              type="password"
              className={INPUT}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">Confirm new password</label>
            <input
              required
              type="password"
              className={INPUT}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
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

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isSubmitting ? "Changing…" : "Change password"}
          </button>
        </form>
      </div>
    </div>
  );
}
