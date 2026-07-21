"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { apiRequest } from "@/lib/api";
import type { MeetingRsvpDetail } from "@/types/api";

function formatWhen(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const dateStr = start.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const startTime = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${dateStr}, ${startTime} – ${endTime}`;
}

function MeetingRsvpContent() {
  const params = useParams<{ token: string }>();
  const searchParams = useSearchParams();
  const token = params.token;
  const preselect = searchParams.get("action");

  const [meeting, setMeeting] = useState<MeetingRsvpDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [responding, setResponding] = useState(false);
  const [respondError, setRespondError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoadError("This meeting invite link is missing a token.");
      setLoading(false);
      return;
    }
    apiRequest<MeetingRsvpDetail>(`/api/v1/meeting-rsvp/${token}`, { method: "GET" })
      .then(setMeeting)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "This invite link is invalid or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  async function respond(response_status: "accepted" | "declined") {
    setResponding(true);
    setRespondError(null);
    try {
      const updated = await apiRequest<MeetingRsvpDetail>(`/api/v1/meeting-rsvp/${token}/respond`, {
        method: "POST",
        body: { response_status },
      });
      setMeeting(updated);
    } catch (err) {
      setRespondError(err instanceof Error ? err.message : "Failed to record your response.");
    } finally {
      setResponding(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <section className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="glow-badge flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-lg font-bold text-on-primary">
            B
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">BiznizFlowPilot</h1>
            <p className="text-xs text-muted">Meeting invite</p>
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-muted">Checking your invite…</p>
        ) : loadError ? (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
            {loadError}
          </p>
        ) : meeting ? (
          <>
            <h2 className="mb-1 text-lg font-semibold text-foreground">{meeting.title}</h2>
            <p className="mb-1 text-sm text-on-surface-variant">{formatWhen(meeting.start_time, meeting.end_time)}</p>
            <p className="mb-4 text-xs text-muted">
              Organized by {meeting.organizer_name || "—"} · {meeting.call_type === "video" ? "Video call" : "Voice call"}
            </p>
            {meeting.description && (
              <p className="mb-4 rounded-md border border-border bg-background px-3 py-2 text-sm text-on-surface-variant">
                {meeting.description}
              </p>
            )}

            {meeting.response_status !== "pending" && (
              <p
                className={`mb-4 rounded-md border px-3 py-2 text-sm ${
                  meeting.response_status === "accepted"
                    ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-400"
                    : "border-rose-900/40 bg-rose-950/30 text-rose-400"
                }`}
              >
                You have {meeting.response_status} this invite.
              </p>
            )}

            {respondError && (
              <p className="mb-4 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
                {respondError}
              </p>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                disabled={responding}
                onClick={() => respond("accepted")}
                className={`erp-button-primary flex-1 px-4 py-2 text-sm font-semibold disabled:opacity-60 ${
                  preselect === "accept" ? "ring-2 ring-emerald-500" : ""
                }`}
              >
                Accept
              </button>
              <button
                type="button"
                disabled={responding}
                onClick={() => respond("declined")}
                className={`flex-1 rounded-lg border border-border px-4 py-2 text-sm font-semibold text-foreground transition-colors hover:border-rose-500/60 ${
                  preselect === "decline" ? "ring-2 ring-rose-500" : ""
                }`}
              >
                Decline
              </button>
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}

export default function MeetingRsvpPage() {
  return (
    <Suspense fallback={null}>
      <MeetingRsvpContent />
    </Suspense>
  );
}
