"use client";

import { useState } from "react";

import {
  borderClass,
  closeButtonClass,
  floatingPanelClass,
  floatingPanelHoverClass,
  inputClass,
  mutedClass,
  textClass,
  type EmailTheme,
} from "./emailTheme";

export interface ComposeDraft {
  to: string;
  cc: string;
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
  theme,
}: {
  state: "open" | "minimized";
  draft: ComposeDraft;
  onDraftChange: (patch: Partial<ComposeDraft>) => void;
  onMinimize: () => void;
  onExpand: () => void;
  onClose: () => void;
  onSend: (to: string, subject: string, body: string, cc: string[]) => Promise<void>;
  theme: EmailTheme;
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
      const cc = draft.cc.split(",").map((s) => s.trim()).filter(Boolean);
      await onSend(draft.to.trim(), draft.subject.trim(), draft.body.trim(), cc);
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
        className={`fixed bottom-6 right-6 z-50 flex w-72 items-center justify-between rounded-xl border px-4 py-3 text-left shadow-2xl ${floatingPanelClass(theme)} ${floatingPanelHoverClass(theme)}`}
      >
        <span className={`truncate text-sm font-medium ${textClass(theme)}`}>
          {draft.subject.trim() || "New message"}
        </span>
        <span
          role="button"
          tabIndex={0}
          aria-label="Close"
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onClose(); } }}
          className={`ml-2 shrink-0 ${closeButtonClass(theme)}`}
        >
          ×
        </span>
      </button>
    );
  }

  return (
    <div className={`fixed bottom-6 right-6 z-50 w-[420px] overflow-hidden rounded-2xl border shadow-2xl ${floatingPanelClass(theme)}`}>
      <div className={`flex items-center justify-between border-b px-4 py-3 ${borderClass(theme)}`}>
        <h2 className={`text-sm font-semibold ${textClass(theme)}`}>New email</h2>
        <div className="flex items-center gap-3">
          <button type="button" aria-label="Minimize" onClick={onMinimize} className={closeButtonClass(theme)}>
            <span className="material-symbols-outlined text-[18px]">remove</span>
          </button>
          <button type="button" aria-label="Close" onClick={onClose} className={closeButtonClass(theme)}>×</button>
        </div>
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-3 px-4 py-3">
          <div>
            <label className={`mb-1 block text-xs font-medium ${mutedClass(theme)}`}>To</label>
            <input
              autoFocus type="email" value={draft.to} onChange={(e) => onDraftChange({ to: e.target.value })}
              placeholder="recipient@example.com" className={inputClass(theme)}
            />
          </div>
          <div>
            <label className={`mb-1 block text-xs font-medium ${mutedClass(theme)}`}>Cc</label>
            <input
              type="text" value={draft.cc} onChange={(e) => onDraftChange({ cc: e.target.value })}
              placeholder="cc@example.com, another@example.com" className={inputClass(theme)}
            />
          </div>
          <div>
            <label className={`mb-1 block text-xs font-medium ${mutedClass(theme)}`}>Subject</label>
            <input
              value={draft.subject} onChange={(e) => onDraftChange({ subject: e.target.value })}
              placeholder="Subject" className={inputClass(theme)}
            />
          </div>
          <div>
            <label className={`mb-1 block text-xs font-medium ${mutedClass(theme)}`}>Message</label>
            <textarea
              value={draft.body} onChange={(e) => onDraftChange({ body: e.target.value })}
              rows={7} placeholder="Write your message…" className={inputClass(theme)}
            />
          </div>
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </div>
        <div className={`flex justify-end gap-2 border-t px-4 py-3 ${borderClass(theme)}`}>
          <button type="button" onClick={onClose} className={`rounded-md px-4 py-2 text-sm font-medium ${closeButtonClass(theme)}`}>
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
