"use client";

import { useState } from "react";

const INPUT = "erp-input w-full px-3 py-2 text-sm";

export function ComposeModal({
  onSend,
  onClose,
  title = "New email",
  initialSubject = "",
  initialBody = "",
}: {
  onSend: (to: string, subject: string, body: string) => Promise<void>;
  onClose: () => void;
  title?: string;
  initialSubject?: string;
  initialBody?: string;
}) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!to.trim() || !subject.trim() || !body.trim()) {
      setError("Fill in all fields.");
      return;
    }
    setSending(true);
    setError("");
    try {
      await onSend(to.trim(), subject.trim(), body.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
        <form onSubmit={handleSubmit} noValidate>
          <div className="space-y-4 px-6 py-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">To</label>
              <input
                autoFocus type="email" value={to} onChange={(e) => setTo(e.target.value)}
                placeholder="recipient@example.com" className={INPUT}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Subject</label>
              <input
                value={subject} onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject" className={INPUT}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Message</label>
              <textarea
                value={body} onChange={(e) => setBody(e.target.value)}
                rows={8} placeholder="Write your message…" className={INPUT}
              />
            </div>
            {error && <p className="text-sm text-rose-400">{error}</p>}
          </div>
          <div className="flex justify-end gap-2 border-t border-outline-variant px-6 py-4">
            <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-sm font-medium text-slate-400 hover:text-white">
              Cancel
            </button>
            <button type="submit" disabled={sending} className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
              {sending ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
