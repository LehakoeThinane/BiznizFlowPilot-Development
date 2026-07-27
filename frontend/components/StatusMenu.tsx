"use client";

import { useState } from "react";

import { apiRequest } from "@/lib/api";
import { PRESENCE_PRESETS } from "@/lib/presence";
import type { CurrentUser, Presence, PresenceStatus } from "@/types/api";

interface StatusMenuProps {
  user: CurrentUser | null;
  onUpdated: (presence: Presence) => void;
}

export function StatusMenu({ user, onUpdated }: StatusMenuProps) {
  const [showCustom, setShowCustom] = useState(false);
  const [customText, setCustomText] = useState(user?.status_text ?? "");
  const [saving, setSaving] = useState(false);

  const currentStatus: PresenceStatus | null | undefined = user?.status;

  async function setStatus(status: string, statusText?: string | null) {
    setSaving(true);
    try {
      const presence = await apiRequest<Presence>("/api/v1/users/me/status", {
        method: "PATCH",
        body: { status, status_text: statusText ?? null },
      });
      onUpdated(presence);
      setShowCustom(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update status.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border-b border-outline-variant py-1">
      <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant">
        Status
      </p>
      {PRESENCE_PRESETS.map((preset) => (
        <button
          key={preset.value}
          type="button"
          disabled={saving}
          onClick={() => setStatus(preset.value)}
          className="flex w-full items-center gap-3 px-4 py-2 text-sm text-on-surface-variant transition-colors hover:bg-white/5 disabled:opacity-50"
        >
          <span className={`h-2.5 w-2.5 rounded-full ${preset.dot}`} />
          <span className="flex-1 text-left">{preset.label}</span>
          {currentStatus === preset.value && (
            <span className="material-symbols-outlined text-[16px] text-emerald-400">check</span>
          )}
        </button>
      ))}

      {!showCustom ? (
        <button
          type="button"
          onClick={() => setShowCustom(true)}
          className="flex w-full items-center gap-3 px-4 py-2 text-sm text-on-surface-variant transition-colors hover:bg-white/5"
        >
          <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
          <span className="flex-1 text-left">
            {currentStatus === "custom" && user?.status_text ? user.status_text : "Custom status…"}
          </span>
          {currentStatus === "custom" && (
            <span className="material-symbols-outlined text-[16px] text-emerald-400">check</span>
          )}
        </button>
      ) : (
        <div className="px-4 py-2">
          <input
            autoFocus
            type="text"
            maxLength={100}
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Out of office, may not respond"
            className="w-full rounded-md border border-outline-variant bg-[#0a1528] px-2 py-1.5 text-sm text-white outline-none focus:border-primary-fixed-dim"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={saving || !customText.trim()}
              onClick={() => setStatus("custom", customText.trim())}
              className="flex-1 rounded-md bg-primary-container px-2 py-1 text-xs font-semibold text-on-primary-container disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setShowCustom(false)}
              className="rounded-md px-2 py-1 text-xs text-on-surface-variant hover:bg-white/5"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
