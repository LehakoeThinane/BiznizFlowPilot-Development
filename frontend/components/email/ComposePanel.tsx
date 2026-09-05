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

const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
  onSend: (to: string, subject: string, body: string, cc: string[], attachments: File[]) => Promise<void>;
  theme: EmailTheme;
}) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);

  function handleFilesChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(e.target.files ?? []);
    e.target.value = "";
    const oversized = chosen.find((f) => f.size > MAX_ATTACHMENT_BYTES);
    if (oversized) {
      setError(`'${oversized.name}' exceeds the 20MB attachment limit.`);
      return;
    }
    setAttachments((prev) => [...prev, ...chosen]);
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

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
      await onSend(draft.to.trim(), draft.subject.trim(), draft.body.trim(), cc, attachments);
      setAttachments([]);
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
        className={`fixed bottom-2 right-2 z-50 flex w-[calc(100vw-1rem)] max-w-72 items-center justify-between rounded-xl border px-4 py-3 text-left shadow-2xl sm:bottom-6 sm:right-6 ${floatingPanelClass(theme)} ${floatingPanelHoverClass(theme)}`}
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
    <div className={`fixed bottom-2 right-2 z-50 max-h-[calc(100vh-1rem)] w-[calc(100vw-1rem)] overflow-y-auto rounded-2xl border shadow-2xl sm:bottom-6 sm:right-6 sm:w-[420px] ${floatingPanelClass(theme)}`}>
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
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {attachments.map((file, i) => (
                <span
                  key={`${file.name}-${i}`}
                  className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs ${theme === "dark" ? "border-outline-variant bg-white/5 text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"
                    }`}
                >
                  <span className="material-symbols-outlined text-[14px]">attach_file</span>
                  <span className="max-w-[160px] truncate">{file.name}</span>
                  <span className="text-slate-500">({formatBytes(file.size)})</span>
                  <button
                    type="button"
                    aria-label={`Remove ${file.name}`}
                    onClick={() => removeAttachment(i)}
                    className="ml-1 text-slate-400 hover:text-slate-200"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </div>
        <div className={`flex items-center justify-between gap-2 border-t px-4 py-3 ${borderClass(theme)}`}>
          <label
            className={`flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium ${closeButtonClass(theme)}`}
            aria-label="Attach files"
          >
            <span className="material-symbols-outlined text-[18px]">attach_file</span>
            <input type="file" multiple onChange={handleFilesChosen} className="hidden" />
          </label>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className={`rounded-md px-4 py-2 text-sm font-medium ${closeButtonClass(theme)}`}>
              Discard
            </button>
            <button type="submit" disabled={sending} className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
              {sending ? "Sending…" : "Send"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
