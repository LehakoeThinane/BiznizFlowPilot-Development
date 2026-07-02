"use client";

import { FormEvent, useContext, useRef, useState } from "react";

import { apiRequest } from "@/lib/api";
import { UserContext } from "@/contexts/UserContext";

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

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-[#aaa]">{label}</label>
      {children}
    </div>
  );
}

function Alert({ ok, text }: { ok: boolean; text: string }) {
  return (
    <p className={`rounded-md border px-3 py-2 text-sm ${
      ok ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-400"
         : "border-red-900/40 bg-red-950/30 text-red-400"
    }`}>
      {text}
    </p>
  );
}

export default function SettingsPage() {
  const { user, setUser } = useContext(UserContext);
  const fileRef = useRef<HTMLInputElement>(null);

  const [firstName, setFirstName] = useState(user?.full_name?.split(" ")[0] ?? "");
  const [lastName, setLastName] = useState(user?.full_name?.split(" ").slice(1).join(" ") ?? "");
  const [avatarPreview, setAvatarPreview] = useState<string | null>(user?.avatar_url ?? null);
  const [avatarData, setAvatarData] = useState<string | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setProfileMsg({ ok: false, text: "Image must be under 2 MB." });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      setAvatarPreview(result);
      setAvatarData(result);
    };
    reader.readAsDataURL(file);
  }

  async function handleProfileSave(e: FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      const body: Record<string, unknown> = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      };
      if (avatarData !== null) body.avatar_url = avatarData;

      const updated = await apiRequest<{
        full_name: string; email: string; role: string;
        user_id: string; business_id: string; avatar_url?: string | null;
      }>("/api/v1/users/me", {
        method: "PATCH",
        body,
      });
      if (user) setUser({ ...user, full_name: updated.full_name, avatar_url: updated.avatar_url });
      setAvatarData(null);
      setProfileMsg({ ok: true, text: "Profile updated." });
    } catch (err) {
      setProfileMsg({ ok: false, text: err instanceof Error ? err.message : "Update failed." });
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange(e: FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    if (newPw.length < 8) {
      setPwMsg({ ok: false, text: "New password must be at least 8 characters." });
      return;
    }
    if (newPw !== confirmPw) {
      setPwMsg({ ok: false, text: "New passwords do not match." });
      return;
    }
    setPwSaving(true);
    try {
      await apiRequest("/api/v1/users/me/change-password", {
        method: "POST",
        body: { current_password: currentPw, new_password: newPw },
      });
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      setPwMsg({ ok: true, text: "Password changed successfully." });
    } catch (err) {
      setPwMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to change password." });
    } finally {
      setPwSaving(false);
    }
  }

  const initials = (user?.full_name ?? "?")
    .split(" ").slice(0, 2).map((w) => w[0] ?? "").join("").toUpperCase();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Settings</h1>
        <p className="mt-1 text-sm text-[#888]">Manage your account and preferences</p>
      </div>

      {/* ── Account overview ── */}
      <Section title="Account">
        <div className="flex items-center gap-4">
          {avatarPreview ? (
            <img src={avatarPreview} alt="avatar" className="h-14 w-14 shrink-0 rounded-full object-cover" />
          ) : (
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary-container text-lg font-bold text-on-primary-container">
              {initials || "?"}
            </div>
          )}
          <div>
            <p className="text-sm font-semibold text-white">{user?.full_name ?? "—"}</p>
            <p className="text-xs text-[#888]">{user?.email ?? ""}</p>
            <span className="mt-1 inline-block rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-medium capitalize text-on-primary-container">
              {user?.role ?? ""}
            </span>
          </div>
        </div>
      </Section>

      {/* ── Profile ── */}
      <Section title="Profile">
        <form onSubmit={handleProfileSave} className="space-y-5">

          {/* Avatar */}
          <div className="flex items-center gap-4">
            <div className="relative shrink-0">
              {avatarPreview ? (
                <img src={avatarPreview} alt="avatar" className="h-16 w-16 rounded-full object-cover" />
              ) : (
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-container text-xl font-bold text-on-primary-container">
                  {initials || "?"}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="rounded-md border border-[#333] px-3 py-1.5 text-xs font-medium text-[#aaa] hover:border-[#555] hover:text-white transition-colors"
              >
                {avatarPreview ? "Change photo" : "Upload photo"}
              </button>
              {avatarPreview && (
                <button
                  type="button"
                  onClick={() => { setAvatarPreview(null); setAvatarData(""); }}
                  className="text-xs text-rose-400 hover:text-rose-300 transition-colors"
                >
                  Remove photo
                </button>
              )}
              <p className="text-[11px] text-[#555]">JPG, PNG or GIF · max 2 MB</p>
            </div>
          </div>

          {/* Name */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="First name" id="s-first-name">
              <input id="s-first-name" type="text" required value={firstName}
                onChange={(e) => setFirstName(e.target.value)} className={INPUT} placeholder="First name" />
            </Field>
            <Field label="Last name" id="s-last-name">
              <input id="s-last-name" type="text" required value={lastName}
                onChange={(e) => setLastName(e.target.value)} className={INPUT} placeholder="Last name" />
            </Field>
          </div>

          <Field label="Email" id="s-email">
            <input id="s-email" type="email" value={user?.email ?? ""} disabled
              placeholder="Email address" className={`${INPUT} opacity-50 cursor-not-allowed`} />
            <p className="mt-1 text-xs text-[#555]">Email changes are not supported at this time.</p>
          </Field>

          {profileMsg && <Alert ok={profileMsg.ok} text={profileMsg.text} />}

          <div className="flex justify-end">
            <button type="submit" disabled={profileSaving}
              className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
              {profileSaving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </Section>

      {/* ── Change password ── */}
      <Section title="Change password">
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <Field label="Current password" id="s-current-pw">
            <input id="s-current-pw" type="password" required value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)} className={INPUT}
              autoComplete="current-password" placeholder="Enter current password" />
          </Field>
          <Field label="New password" id="s-new-pw">
            <input id="s-new-pw" type="password" required minLength={8} value={newPw}
              onChange={(e) => setNewPw(e.target.value)} className={INPUT}
              autoComplete="new-password" placeholder="At least 8 characters" />
          </Field>
          <Field label="Confirm new password" id="s-confirm-pw">
            <input id="s-confirm-pw" type="password" required value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)} className={INPUT}
              autoComplete="new-password" placeholder="Repeat new password" />
          </Field>
          {pwMsg && <Alert ok={pwMsg.ok} text={pwMsg.text} />}
          <div className="flex justify-end">
            <button type="submit" disabled={pwSaving}
              className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
              {pwSaving ? "Changing…" : "Change password"}
            </button>
          </div>
        </form>
      </Section>
    </div>
  );
}
