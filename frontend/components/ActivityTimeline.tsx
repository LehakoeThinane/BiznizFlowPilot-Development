"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import type {
  BusinessDocument,
  BusinessEvent,
  BusinessUser,
  BusinessUserListResponse,
  DocumentDownloadResponse,
  DocumentListResponse,
  EventListResponse,
} from "@/types/api";

const EVENT_TYPE_LABELS: Record<string, string> = {
  lead_created: "Lead Created", lead_updated: "Lead Updated",
  lead_status_changed: "Status Changed", lead_assigned: "Assigned",
  lead_deleted: "Lead Deleted", lead_idle: "Lead Idle",
  task_created: "Task Created", task_updated: "Task Updated",
  task_assigned: "Assigned", task_completed: "Completed",
  task_deleted: "Task Deleted", task_overdue: "Overdue",
  custom: "Note",
};

function prettify(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function eventColor(type: string): string {
  if (type === "custom") return "bg-emerald-500/20 text-emerald-300";
  if (type.endsWith("_created")) return "bg-blue-500/20 text-blue-300";
  if (type.endsWith("_deleted")) return "bg-rose-500/20 text-rose-300";
  if (type.endsWith("_completed")) return "bg-emerald-500/20 text-emerald-300";
  if (type.endsWith("_assigned")) return "bg-violet-500/20 text-violet-300";
  return "bg-white/10 text-slate-300";
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ActivityTimeline({ entityType, entityId }: { entityType: string; entityId: string }) {
  const [events, setEvents] = useState<BusinessEvent[]>([]);
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [users, setUsers] = useState<BusinessUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [isPosting, setIsPosting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const token = getStoredToken();

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiRequest<EventListResponse>(
        `/api/v1/events?entity_type=${encodeURIComponent(entityType)}&entity_id=${entityId}&limit=100`,
        { authToken: token },
      ),
      apiRequest<DocumentListResponse>(
        `/api/v1/documents?entity_type=${encodeURIComponent(entityType)}&entity_id=${entityId}`,
        { authToken: token },
      ).catch(() => ({ total: 0, items: [] })),
      apiRequest<BusinessUserListResponse>("/api/v1/users?skip=0&limit=200", { authToken: token }).catch(
        () => ({ total: 0, items: [] }),
      ),
    ])
      .then(([eventsResp, docsResp, usersResp]) => {
        setEvents(eventsResp.items ?? []);
        setDocuments(docsResp.items ?? []);
        setUsers(usersResp.items ?? []);
      })
      .catch((e: unknown) => {
        setEvents([]);
        setError(e instanceof Error ? e.message : "Failed to load activity");
      })
      .finally(() => setLoading(false));
  }, [entityType, entityId, token]);

  useEffect(() => {
    load();
  }, [load]);

  function resolveActor(actorId: string | null): string {
    if (!actorId) return "System";
    const match = users.find((u) => u.id === actorId);
    return match ? `${match.first_name} ${match.last_name}`.trim() || match.email : "Someone";
  }

  async function handlePostNote() {
    const text = note.trim();
    if (!text) return;
    setIsPosting(true);
    setError(null);
    try {
      await apiRequest<BusinessEvent>("/api/v1/events", {
        method: "POST",
        authToken: token,
        body: {
          event_type: "custom",
          entity_type: entityType,
          entity_id: entityId,
          description: text,
        },
      });
      setNote("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to post note");
    } finally {
      setIsPosting(false);
    }
  }

  async function handleFileSelected(file: File | undefined) {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("entity_type", entityType);
      formData.append("entity_id", entityId);
      formData.append("file", file);
      await apiRequest<BusinessDocument>("/api/v1/documents", {
        method: "POST",
        authToken: token,
        body: formData,
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload file");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDownload(doc: BusinessDocument) {
    setBusyDocId(doc.id);
    setError(null);
    try {
      const { url } = await apiRequest<DocumentDownloadResponse>(
        `/api/v1/documents/${doc.id}/download-url`,
        { authToken: token },
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to get download link");
    } finally {
      setBusyDocId(null);
    }
  }

  async function handleDeleteDocument(doc: BusinessDocument) {
    if (!confirm(`Delete "${doc.filename}"?`)) return;
    setBusyDocId(doc.id);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/documents/${doc.id}`, { method: "DELETE", authToken: token });
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete file");
    } finally {
      setBusyDocId(null);
    }
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-muted">Attachments</p>
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="rounded-md border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
        >
          {isUploading ? "Uploading…" : "+ Attach file"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => void handleFileSelected(e.target.files?.[0])}
        />
      </div>

      {documents.length > 0 && (
        <div className="mb-4 space-y-1.5">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between gap-2 rounded-md border border-border bg-white/5 px-3 py-2 text-sm"
            >
              <button
                type="button"
                onClick={() => void handleDownload(doc)}
                disabled={busyDocId === doc.id}
                className="min-w-0 flex-1 truncate text-left text-[#ddd] hover:text-white hover:underline disabled:opacity-40"
                title={doc.filename}
              >
                {doc.filename}
              </button>
              <span className="shrink-0 text-xs text-muted">{formatSize(doc.size_bytes)}</span>
              <button
                type="button"
                onClick={() => void handleDeleteDocument(doc)}
                disabled={busyDocId === doc.id}
                className="shrink-0 text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="mb-2 text-xs uppercase tracking-wide text-muted">Activity</p>

      <div className="mb-3 flex items-start gap-2">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handlePostNote();
            }
          }}
          rows={2}
          placeholder="Log a note… (Enter to post, Shift+Enter for newline)"
          className="erp-input flex-1 resize-none px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={() => void handlePostNote()}
          disabled={!note.trim() || isPosting}
          className="erp-button-primary shrink-0 px-3 py-2 text-sm font-semibold disabled:opacity-40"
        >
          {isPosting ? "…" : "Post"}
        </button>
      </div>

      {error && <p className="mb-2 text-xs text-rose-400">{error}</p>}

      {loading ? (
        <p className="py-4 text-center text-xs text-muted">Loading…</p>
      ) : events.length === 0 ? (
        <p className="py-4 text-center text-xs text-muted">No activity yet.</p>
      ) : (
        <div className="max-h-96 space-y-3 overflow-y-auto rounded-md border border-border bg-white/5 p-3">
          {events.map((ev) => (
            <div key={ev.id} className="flex items-start gap-3 text-sm">
              <span
                className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${eventColor(ev.event_type)}`}
              >
                {EVENT_TYPE_LABELS[ev.event_type] ?? prettify(ev.event_type)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="whitespace-pre-wrap text-[#ddd]">{ev.description ?? prettify(ev.event_type)}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {resolveActor(ev.actor_id)} · {formatTime(ev.created_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
