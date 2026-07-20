"use client";

import { useState } from "react";

const INPUT = "erp-input w-full px-3 py-2 text-sm";

export function PollComposerModal({
  onCreate,
  onClose,
}: {
  onCreate: (question: string, options: string[], allowMultiple: boolean) => Promise<void>;
  onClose: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState(["", ""]);
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function updateOption(index: number, value: string) {
    setOptions((prev) => prev.map((o, i) => (i === index ? value : o)));
  }

  function addOption() {
    if (options.length >= 10) return;
    setOptions((prev) => [...prev, ""]);
  }

  function removeOption(index: number) {
    if (options.length <= 2) return;
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleanOptions = options.map((o) => o.trim()).filter(Boolean);
    if (!question.trim()) {
      setError("Enter a question.");
      return;
    }
    if (cleanOptions.length < 2) {
      setError("Add at least 2 options.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onCreate(question.trim(), cleanOptions, allowMultiple);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create poll.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Create poll</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
        <form onSubmit={handleSubmit} noValidate>
          <div className="max-h-[26rem] space-y-4 overflow-y-auto px-6 py-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Question</label>
              <input autoFocus value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question…" className={INPUT} />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-400">Options</label>
              <div className="space-y-2">
                {options.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      value={opt}
                      onChange={(e) => updateOption(i, e.target.value)}
                      placeholder={`Option ${i + 1}`}
                      className={INPUT}
                    />
                    {options.length > 2 && (
                      <button type="button" onClick={() => removeOption(i)} aria-label="Remove option" className="shrink-0 text-slate-500 hover:text-white">
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {options.length < 10 && (
                <button type="button" onClick={addOption} className="mt-2 text-xs font-medium text-blue-400 hover:text-blue-300">
                  + Add option
                </button>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={allowMultiple} onChange={(e) => setAllowMultiple(e.target.checked)} />
              Allow multiple answers
            </label>

            {error && <p className="text-xs text-rose-400">{error}</p>}
          </div>
          <div className="flex justify-end gap-2 border-t border-outline-variant px-6 py-4">
            <button type="button" onClick={onClose} className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="erp-button-primary px-4 py-2 text-sm font-medium disabled:opacity-50">
              {submitting ? "Creating…" : "Create poll"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
