"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Meeting, MeetingCallType, MeetingListResponse } from "@/types/api";

const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;

function formatMeetingTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function EventComposerModal({
  token,
  onShareExisting,
  onScheduleNew,
  onClose,
}: {
  token: string | null;
  onShareExisting: (meetingId: string) => Promise<void>;
  onScheduleNew: (data: { title: string; description: string; start: string; end: string; call_type: MeetingCallType }) => Promise<void>;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"share" | "schedule">("share");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loadingMeetings, setLoadingMeetings] = useState(true);
  const [sharing, setSharing] = useState<string | null>(null);

  const [form, setForm] = useState({ title: "", description: "", start: "", end: "", call_type: "video" as MeetingCallType });
  const [scheduling, setScheduling] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<MeetingListResponse>("/api/v1/meetings", { authToken: token, query: { limit: 20 } })
      .then((d) => setMeetings((d.items ?? []).filter((m) => m.status === "scheduled")))
      .catch(console.error)
      .finally(() => setLoadingMeetings(false));
  }, [token]);

  async function handleShare(meetingId: string) {
    setSharing(meetingId);
    try {
      await onShareExisting(meetingId);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to share event.");
    } finally {
      setSharing(null);
    }
  }

  async function handleSchedule(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.start || !form.end) {
      setError("Title, start, and end time are required.");
      return;
    }
    setScheduling(true);
    setError("");
    try {
      await onScheduleNew(form);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to schedule event.");
    } finally {
      setScheduling(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Event</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>

        <div className="flex border-b border-outline-variant">
          <button
            type="button"
            onClick={() => setTab("share")}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === "share" ? "border-b-2 border-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Share upcoming
          </button>
          <button
            type="button"
            onClick={() => setTab("schedule")}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === "schedule" ? "border-b-2 border-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Schedule new
          </button>
        </div>

        {tab === "share" ? (
          <div className="max-h-80 overflow-y-auto py-2">
            {loadingMeetings ? (
              <div className="px-6 py-8 text-center text-xs text-slate-500">Loading…</div>
            ) : meetings.length === 0 ? (
              <p className="px-6 py-8 text-center text-sm text-slate-500">No upcoming meetings. Schedule a new one instead.</p>
            ) : (
              meetings.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  disabled={sharing === m.id}
                  onClick={() => handleShare(m.id)}
                  className="flex w-full items-center gap-3 px-6 py-2.5 text-left transition-colors hover:bg-white/5 disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-red-400">event</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-white">{m.title}</p>
                    <p className="truncate text-xs text-slate-500">{formatMeetingTime(m.start_time)}</p>
                  </div>
                  {sharing === m.id && <span className="text-xs text-slate-500">…</span>}
                </button>
              ))
            )}
            {error && <p className="px-6 pb-2 text-xs text-rose-400">{error}</p>}
          </div>
        ) : (
          <form onSubmit={handleSchedule} noValidate>
            <div className="max-h-[26rem] space-y-3 overflow-y-auto px-6 py-4">
              <input
                autoFocus
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Title"
                className={INPUT}
              />
              <textarea
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Description (optional)"
                rows={2}
                className={`${INPUT} resize-none`}
              />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">Start</label>
                  <input type="datetime-local" value={form.start} onChange={(e) => setForm((f) => ({ ...f, start: e.target.value }))} className={INPUT} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">End</label>
                  <input type="datetime-local" value={form.end} onChange={(e) => setForm((f) => ({ ...f, end: e.target.value }))} className={INPUT} />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Call type</label>
                <select value={form.call_type} onChange={(e) => setForm((f) => ({ ...f, call_type: e.target.value as MeetingCallType }))} className={SELECT}>
                  <option value="video">Video</option>
                  <option value="voice">Voice</option>
                </select>
              </div>
              {error && <p className="text-xs text-rose-400">{error}</p>}
            </div>
            <div className="flex justify-end gap-2 border-t border-outline-variant px-6 py-4">
              <button type="button" onClick={onClose} className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20">
                Cancel
              </button>
              <button type="submit" disabled={scheduling} className="erp-button-primary px-4 py-2 text-sm font-medium disabled:opacity-50">
                {scheduling ? "Scheduling…" : "Schedule & share"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
