"use client";

import { useState } from "react";

const INPUT = "erp-input w-full px-3 py-2 text-sm";

export interface ComposeDraft {
  to: string;
  subject: string;
  body: string;
}

export function ComposePanel({
  state,
  draft,
  onDraftChange,
  onMinimize,
  onExpand,
  onClose,
  onSend,
}: {
  state: "open" | "minimized";
  draft: ComposeDraft;
  onDraftChange: (patch: Partial<ComposeDraft>) => void;
  onMinimize: () => void;
  onExpand: () => void;
  onClose: () => void;
  onSend: (to: string, subject: string, body: string) => Promise<void>;
}) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.to.trim() || !draft.subject.trim() || !draft.body.trim()) {
      setError("Fill in all fields.");
      return;
    }
    setSending(true);
    setError("");
    try {
      await onSend(draft.to.trim(), draft.subject.trim(), draft.body.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send.");
    } finally {
      setSending(false);
    }
  }

  if (state === "minimized") {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="fixed bottom-6 right-6 z-50 flex w-72 items-center justify-between rounded-xl border border-outline-variant bg-[#0f1c33] px-4 py-3 text-left shadow-2xl hover:bg-[#132038]"
      >
        <span className="truncate text-sm font-medium text-white">
          {draft.subject.trim() || "New message"}
        </span>
        <span
          role="button"
          tabIndex={0}
          aria-label="Close"
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onClose(); } }}
          className="ml-2 shrink-0 text-slate-400 hover:text-white"
        >
          ×
        </span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[420px] overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
      <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3">
        <h2 className="text-sm font-semibold text-white">New email</h2>
        <div className="flex items-center gap-3">
          <button type="button" aria-label="Minimize" onClick={onMinimize} className="text-slate-400 hover:text-white">
            <span className="material-symbols-outlined text-[18px]">remove</span>
          </button>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-3 px-4 py-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">To</label>
            <input
              autoFocus type="email" value={draft.to} onChange={(e) => onDraftChange({ to: e.target.value })}
              placeholder="recipient@example.com" className={INPUT}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Subject</label>
            <input
              value={draft.subject} onChange={(e) => onDraftChange({ subject: e.target.value })}
              placeholder="Subject" className={INPUT}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Message</label>
            <textarea
              value={draft.body} onChange={(e) => onDraftChange({ body: e.target.value })}
              rows={7} placeholder="Write your message…" className={INPUT}
            />
          </div>
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-outline-variant px-4 py-3">
          <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-sm font-medium text-slate-400 hover:text-white">
            Discard
          </button>
          <button type="submit" disabled={sending} className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
