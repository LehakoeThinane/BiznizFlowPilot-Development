"use client";

import { useState } from "react";

import { apiRequest } from "@/lib/api";
import type { ChatAction } from "@/types/api";

const STATUS_LABEL: Record<ChatAction["status"], string> = {
  pending: "Pending",
  confirmed: "Confirmed…",
  cancelled: "Cancelled",
  executed: "Done",
  failed: "Failed",
};

const STATUS_CLASS: Record<ChatAction["status"], string> = {
  pending: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  confirmed: "border-slate-500/40 bg-slate-500/10 text-slate-300",
  cancelled: "border-slate-500/40 bg-slate-500/10 text-slate-400",
  executed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  failed: "border-rose-500/40 bg-rose-500/10 text-rose-300",
};

export function ActionCard({
  messageId,
  action,
  onUpdate,
}: {
  messageId: string;
  action: ChatAction;
  onUpdate: (updated: ChatAction) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function respond(verb: "confirm" | "cancel") {
    setBusy(true);
    setError(null);
    try {
      const resp = await apiRequest<{ message_id: string; action: ChatAction }>(
        `/api/v1/chat/messages/${messageId}/actions/${action.id}/${verb}`,
        { method: "POST" },
      );
      onUpdate(resp.action);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${verb} action.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 rounded-lg border border-outline-variant/60 bg-black/20 p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-slate-200">{action.description}</p>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_CLASS[action.status]}`}>
          {STATUS_LABEL[action.status]}
        </span>
      </div>

      {action.status === "pending" && (
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => respond("confirm")}
            className="rounded-md bg-brand px-3 py-1 text-xs font-semibold text-white disabled:opacity-60"
          >
            Confirm
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => respond("cancel")}
            className="rounded-md border border-outline-variant px-3 py-1 text-xs font-medium text-slate-300 disabled:opacity-60"
          >
            Cancel
          </button>
        </div>
      )}

      {action.status === "failed" && action.error && (
        <p className="mt-2 text-xs text-rose-400">{action.error}</p>
      )}
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </div>
  );
}
