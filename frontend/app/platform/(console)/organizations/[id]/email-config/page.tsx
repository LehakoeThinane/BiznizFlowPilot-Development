"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { platformApiRequest } from "@/lib/platform-api";
import type { OrganizationEmailConfig, OrganizationEmailConfigUpdate } from "@/types/api";

const INPUT = "w-full rounded-md border border-[#2a2a3a] bg-[#151520] px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

export default function PlatformOrganizationEmailConfigPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [config, setConfig] = useState<OrganizationEmailConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFromEmail, setSmtpFromEmail] = useState("");
  const [smtpFromName, setSmtpFromName] = useState("");

  function load() {
    platformApiRequest<OrganizationEmailConfig>(`/platform/v1/organizations/${params.id}/email-config`)
      .then((data) => {
        setConfig(data);
        setSmtpHost(data.smtp_host ?? "");
        setSmtpPort(data.smtp_port?.toString() ?? "587");
        setSmtpUsername(data.smtp_username ?? "");
        setSmtpFromEmail(data.smtp_from_email ?? "");
        setSmtpFromName(data.smtp_from_name ?? "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load email config"));
  }

  useEffect(load, [params.id]);

  async function handleSave() {
    setSaveError(null);
    setSaveSuccess(null);
    setIsSaving(true);
    const body: OrganizationEmailConfigUpdate = {
      smtp_host: smtpHost.trim(),
      smtp_port: Number(smtpPort),
      smtp_username: smtpUsername.trim(),
      smtp_from_email: smtpFromEmail.trim(),
      smtp_from_name: smtpFromName.trim(),
    };
    if (smtpPassword.trim()) body.smtp_password = smtpPassword.trim();

    try {
      const updated = await platformApiRequest<OrganizationEmailConfig>(
        `/platform/v1/organizations/${params.id}/email-config`,
        { method: "PUT", body },
      );
      setConfig(updated);
      setSmtpPassword("");
      setSaveSuccess("Email sender saved.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClear() {
    if (!window.confirm("Revert this organization to the platform default email sender?")) return;
    setSaveError(null);
    setSaveSuccess(null);
    setIsClearing(true);
    try {
      await platformApiRequest(`/platform/v1/organizations/${params.id}/email-config`, { method: "DELETE" });
      setSmtpHost(""); setSmtpPort("587"); setSmtpUsername(""); setSmtpPassword("");
      setSmtpFromEmail(""); setSmtpFromName("");
      setConfig({
        smtp_host: null, smtp_port: null, smtp_username: null,
        smtp_password_set: false, smtp_from_email: null, smtp_from_name: null,
      });
      setSaveSuccess("Reverted to the platform default sender.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to clear email config");
    } finally {
      setIsClearing(false);
    }
  }

  if (error) {
    return <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{error}</p>;
  }
  if (!config) {
    return <p className="text-sm text-[#777]">Loading…</p>;
  }

  return (
    <div className="max-w-2xl">
      <button
        type="button"
        onClick={() => router.push(`/platform/organizations/${params.id}`)}
        className="mb-4 text-xs text-[#777] hover:text-white"
      >
        ← Back to organization
      </button>

      <h1 className="mb-1 text-lg font-semibold text-white">Custom email sender</h1>
      <p className="mb-6 text-sm text-[#777]">
        When configured, this organization&apos;s meeting invites (and future business emails) send from their
        own domain instead of the platform default. Leave unconfigured to keep using the platform sender.
      </p>

      <div className="space-y-4 rounded-xl border border-[#22222e] bg-[#12121a] p-5">
        <div>
          <label className="mb-1 block text-xs font-medium text-[#aaa]">SMTP host</label>
          <input className={INPUT} value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.office365.com" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">SMTP port</label>
            <input
              type="number" min={1} max={65535} className={INPUT}
              value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)}
            />
            <p className="mt-1 text-[11px] text-[#666]">465 = implicit SSL, anything else = STARTTLS</p>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">SMTP username</label>
            <input className={INPUT} value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)} />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[#aaa]">SMTP password</label>
          <input
            type="password" className={INPUT} value={smtpPassword}
            onChange={(e) => setSmtpPassword(e.target.value)}
            placeholder={config.smtp_password_set ? "•••••••• (set - leave blank to keep)" : "Not set"}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">From email</label>
            <input className={INPUT} value={smtpFromEmail} onChange={(e) => setSmtpFromEmail(e.target.value)} placeholder="meetings@theircompany.com" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#aaa]">From name</label>
            <input className={INPUT} value={smtpFromName} onChange={(e) => setSmtpFromName(e.target.value)} />
          </div>
        </div>

        {saveError && (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">{saveError}</p>
        )}
        {saveSuccess && (
          <p className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-400">{saveSuccess}</p>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isSaving ? "Saving..." : "Save changes"}
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={isClearing || !config.smtp_host}
            className="rounded-md border border-[#2a2a3a] px-4 py-2 text-sm font-semibold text-[#aaa] disabled:opacity-40"
          >
            {isClearing ? "Reverting..." : "Revert to platform default"}
          </button>
        </div>
      </div>
    </div>
  );
}
