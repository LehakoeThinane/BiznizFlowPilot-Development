"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest } from "@/lib/api";
import { getCurrentUser, getStoredToken } from "@/lib/auth";
import type {
  BusinessDocument,
  BusinessEvent,
  BusinessUser,
  BusinessUserListResponse,
  DocumentAccessRequest,
  DocumentAccessRequestListResponse,
  DocumentDownloadResponse,
  DocumentListResponse,
  DocumentShareLink,
  DocumentShareLinkListResponse,
  DocumentVersion,
  DocumentVersionListResponse,
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
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ActivityTimeline({ entityType, entityId }: { entityType: string; entityId: string }) {
  const router = useRouter();
  const [events, setEvents] = useState<BusinessEvent[]>([]);
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [users, setUsers] = useState<BusinessUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [isPosting, setIsPosting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);
  const [shareOpenDocId, setShareOpenDocId] = useState<string | null>(null);
  const [shareLinks, setShareLinks] = useState<Record<string, DocumentShareLink[]>>({});
  const [isSharing, setIsSharing] = useState(false);
  const [accessOpenDocId, setAccessOpenDocId] = useState<string | null>(null);
  const [accessRequests, setAccessRequests] = useState<Record<string, DocumentAccessRequest[]>>({});
  const [isManagingAccess, setIsManagingAccess] = useState(false);
  const [versionsOpenDocId, setVersionsOpenDocId] = useState<string | null>(null);
  const [versions, setVersions] = useState<Record<string, DocumentVersion[]>>({});
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkinTargetDocId, setCheckinTargetDocId] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const checkinInputRef = useRef<HTMLInputElement>(null);

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
      getCurrentUser().catch(() => null),
    ])
      .then(([eventsResp, docsResp, usersResp, currentUser]) => {
        setEvents(eventsResp.items ?? []);
        setDocuments(docsResp.items ?? []);
        setUsers(usersResp.items ?? []);
        setCurrentUserId(currentUser?.user_id ?? null);
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

  function handleOpenDocument(doc: BusinessDocument) {
    // In-app composed documents open in the editor, same as clicking
    // "Edit" - there's nothing useful to "download" for these, the raw
    // HTML source isn't a file a user asked to save. Everything else opens
    // inline (see disposition="inline" default in the backend's
    // presigned_download_url) rather than forcing a save-to-disk dialog.
    if (doc.content_type === "text/html") {
      router.push(`/documents/${doc.id}/edit`);
      return;
    }
    void handleDownload(doc);
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

  async function loadShareLinks(docId: string) {
    try {
      const resp = await apiRequest<DocumentShareLinkListResponse>(
        `/api/v1/documents/${docId}/share`,
        { authToken: token },
      );
      setShareLinks((prev) => ({ ...prev, [docId]: resp.items ?? [] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load share links");
    }
  }

  function handleToggleShare(doc: BusinessDocument) {
    if (shareOpenDocId === doc.id) {
      setShareOpenDocId(null);
      return;
    }
    setShareOpenDocId(doc.id);
    void loadShareLinks(doc.id);
  }

  async function handleCreateShareLink(doc: BusinessDocument, expiresInDays: number) {
    setIsSharing(true);
    setError(null);
    try {
      await apiRequest<DocumentShareLink>(`/api/v1/documents/${doc.id}/share`, {
        method: "POST",
        authToken: token,
        body: { expires_in_days: expiresInDays },
      });
      await loadShareLinks(doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create share link");
    } finally {
      setIsSharing(false);
    }
  }

  async function handleRevokeShareLink(doc: BusinessDocument, linkId: string) {
    setIsSharing(true);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/documents/share/${linkId}`, { method: "DELETE", authToken: token });
      await loadShareLinks(doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke share link");
    } finally {
      setIsSharing(false);
    }
  }

  function handleCopyLink(url: string) {
    navigator.clipboard?.writeText(url).catch(() => {});
  }

  async function handleToggleRestricted(doc: BusinessDocument) {
    setBusyDocId(doc.id);
    setError(null);
    try {
      const updated = await apiRequest<BusinessDocument>(`/api/v1/documents/${doc.id}/restrict`, {
        method: "PATCH",
        authToken: token,
        body: { restricted: !doc.restricted },
      });
      setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update restriction");
    } finally {
      setBusyDocId(null);
    }
  }

  async function handleRequestAccess(doc: BusinessDocument) {
    setBusyDocId(doc.id);
    setError(null);
    try {
      await apiRequest<DocumentAccessRequest>(`/api/v1/documents/${doc.id}/access-requests`, {
        method: "POST",
        authToken: token,
      });
      alert("Access requested — you'll be notified once it's reviewed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to request access");
    } finally {
      setBusyDocId(null);
    }
  }

  async function loadAccessRequests(docId: string) {
    try {
      const resp = await apiRequest<DocumentAccessRequestListResponse>(
        `/api/v1/documents/${docId}/access-requests`,
        { authToken: token },
      );
      setAccessRequests((prev) => ({ ...prev, [docId]: resp.items ?? [] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load access requests");
    }
  }

  function handleToggleAccessPanel(doc: BusinessDocument) {
    if (accessOpenDocId === doc.id) {
      setAccessOpenDocId(null);
      return;
    }
    setAccessOpenDocId(doc.id);
    void loadAccessRequests(doc.id);
  }

  async function handleReviewRequest(doc: BusinessDocument, requestId: string, decision: "approve" | "deny") {
    setIsManagingAccess(true);
    setError(null);
    try {
      await apiRequest<DocumentAccessRequest>(`/api/v1/documents/access-requests/${requestId}/${decision}`, {
        method: "POST",
        authToken: token,
      });
      await loadAccessRequests(doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to review access request");
    } finally {
      setIsManagingAccess(false);
    }
  }

  async function handleCheckOut(doc: BusinessDocument) {
    setIsCheckingOut(true);
    setError(null);
    try {
      const updated = await apiRequest<BusinessDocument>(`/api/v1/documents/${doc.id}/checkout`, {
        method: "POST",
        authToken: token,
      });
      setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to check out document");
    } finally {
      setIsCheckingOut(false);
    }
  }

  async function handleCancelCheckout(doc: BusinessDocument) {
    setIsCheckingOut(true);
    setError(null);
    try {
      const updated = await apiRequest<BusinessDocument>(`/api/v1/documents/${doc.id}/checkout/cancel`, {
        method: "POST",
        authToken: token,
      });
      setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to cancel checkout");
    } finally {
      setIsCheckingOut(false);
    }
  }

  function handleStartCheckin(doc: BusinessDocument) {
    setCheckinTargetDocId(doc.id);
    checkinInputRef.current?.click();
  }

  async function handleCheckinFileSelected(file: File | undefined) {
    if (!file || !checkinTargetDocId) return;
    setIsCheckingOut(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const updated = await apiRequest<BusinessDocument>(`/api/v1/documents/${checkinTargetDocId}/checkin`, {
        method: "POST",
        authToken: token,
        body: formData,
      });
      setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      if (versionsOpenDocId === updated.id) void loadVersions(updated.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to check in new version");
    } finally {
      setIsCheckingOut(false);
      setCheckinTargetDocId(null);
      if (checkinInputRef.current) checkinInputRef.current.value = "";
    }
  }

  async function loadVersions(docId: string) {
    try {
      const resp = await apiRequest<DocumentVersionListResponse>(`/api/v1/documents/${docId}/versions`, {
        authToken: token,
      });
      setVersions((prev) => ({ ...prev, [docId]: resp.items ?? [] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load version history");
    }
  }

  function handleToggleVersions(doc: BusinessDocument) {
    if (versionsOpenDocId === doc.id) {
      setVersionsOpenDocId(null);
      return;
    }
    setVersionsOpenDocId(doc.id);
    void loadVersions(doc.id);
  }

  async function handleDownloadVersion(doc: BusinessDocument, versionId: string) {
    setError(null);
    try {
      const { url } = await apiRequest<DocumentDownloadResponse>(
        `/api/v1/documents/${doc.id}/versions/${versionId}/download-url`,
        { authToken: token },
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to get download link for that version");
    }
  }

  return (
    <div>
      <input
        ref={checkinInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.svg,.csv,.txt,.zip"
        className="hidden"
        onChange={(e) => void handleCheckinFileSelected(e.target.files?.[0])}
      />
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
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.svg,.csv,.txt,.zip"
          className="hidden"
          onChange={(e) => void handleFileSelected(e.target.files?.[0])}
        />
      </div>

      {documents.length > 0 && (
        <div className="mb-4 space-y-1.5">
          {documents.map((doc) => (
            <div key={doc.id} className="rounded-md border border-border bg-white/5 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                {doc.has_access ? (
                  <button
                    type="button"
                    onClick={() => handleOpenDocument(doc)}
                    disabled={busyDocId === doc.id}
                    className="min-w-0 flex-1 truncate text-left text-[#ddd] hover:text-white hover:underline disabled:opacity-40"
                    title={doc.filename}
                  >
                    {doc.restricted ? "🔒 " : ""}{doc.filename}
                  </button>
                ) : (
                  <span className="min-w-0 flex-1 truncate text-[#888]" title={doc.filename}>
                    🔒 {doc.filename}
                  </span>
                )}
                <span className="shrink-0 text-xs text-muted">{formatSize(doc.size_bytes)}</span>
                {!doc.has_access && (
                  <button
                    type="button"
                    onClick={() => void handleRequestAccess(doc)}
                    disabled={busyDocId === doc.id}
                    className="shrink-0 rounded border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
                  >
                    Request access
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void handleToggleRestricted(doc)}
                  disabled={busyDocId === doc.id}
                  className="shrink-0 text-xs text-[#ccc] hover:text-white disabled:opacity-40"
                >
                  {doc.restricted ? "Unrestrict" : "Restrict"}
                </button>
                {doc.restricted && (
                  <button
                    type="button"
                    onClick={() => handleToggleAccessPanel(doc)}
                    className="shrink-0 text-xs text-[#8ab4f8] hover:text-[#a9c8ff]"
                  >
                    {accessOpenDocId === doc.id ? "Hide access" : "Access"}
                  </button>
                )}
                {doc.checked_out_by ? (
                  <>
                    <span className="shrink-0 text-xs text-amber-400">
                      {doc.checked_out_by === currentUserId ? "Checked out by you" : "Checked out"}
                    </span>
                    {doc.checked_out_by === currentUserId && (
                      <button
                        type="button"
                        onClick={() => handleStartCheckin(doc)}
                        disabled={isCheckingOut}
                        className="shrink-0 rounded border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
                      >
                        Check in
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void handleCancelCheckout(doc)}
                      disabled={isCheckingOut}
                      className="shrink-0 text-xs text-[#ccc] hover:text-white disabled:opacity-40"
                    >
                      Cancel checkout
                    </button>
                  </>
                ) : (
                  doc.has_access && (
                    <button
                      type="button"
                      onClick={() => void handleCheckOut(doc)}
                      disabled={isCheckingOut}
                      className="shrink-0 rounded border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
                    >
                      Check out
                    </button>
                  )
                )}
                <button
                  type="button"
                  onClick={() => handleToggleVersions(doc)}
                  className="shrink-0 text-xs text-[#8ab4f8] hover:text-[#a9c8ff]"
                >
                  v{doc.version}
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleShare(doc)}
                  className="shrink-0 text-xs text-[#8ab4f8] hover:text-[#a9c8ff]"
                >
                  {shareOpenDocId === doc.id ? "Hide share" : "Share"}
                </button>
                <button
                  type="button"
                  onClick={() => void handleDeleteDocument(doc)}
                  disabled={busyDocId === doc.id}
                  className="shrink-0 text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
                >
                  Delete
                </button>
              </div>

              {versionsOpenDocId === doc.id && (
                <div className="mt-2 space-y-2 border-t border-border pt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#ddd]">Current: {doc.filename} (v{doc.version})</span>
                  </div>
                  {(versions[doc.id] ?? []).length === 0 ? (
                    <p className="text-xs text-muted">No prior versions.</p>
                  ) : (
                    (versions[doc.id] ?? []).map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => void handleDownloadVersion(doc, v.id)}
                        className="flex w-full items-center justify-between gap-2 text-left text-xs text-[#ccc] hover:text-white hover:underline"
                      >
                        <span>v{v.version_number}: {v.filename}</span>
                        <span className="shrink-0 text-muted">{formatTime(v.created_at)}</span>
                      </button>
                    ))
                  )}
                </div>
              )}

              {accessOpenDocId === doc.id && (
                <div className="mt-2 space-y-2 border-t border-border pt-2">
                  {(accessRequests[doc.id] ?? []).length === 0 && (
                    <p className="text-xs text-muted">No access requests yet.</p>
                  )}
                  {(accessRequests[doc.id] ?? []).map((req) => (
                    <div key={req.id} className="flex items-center justify-between gap-2 text-xs">
                      <span className="text-[#ddd]">
                        {resolveActor(req.user_id)} · <span className="capitalize">{req.status}</span>
                      </span>
                      {req.status === "pending" && (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => void handleReviewRequest(doc, req.id, "approve")}
                            disabled={isManagingAccess}
                            className="rounded border border-emerald-700/40 px-2 py-1 text-emerald-400 hover:bg-emerald-900/20 disabled:opacity-40"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleReviewRequest(doc, req.id, "deny")}
                            disabled={isManagingAccess}
                            className="rounded border border-rose-700/40 px-2 py-1 text-rose-400 hover:bg-rose-900/20 disabled:opacity-40"
                          >
                            Deny
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {shareOpenDocId === doc.id && (
                <div className="mt-2 space-y-2 border-t border-border pt-2">
                  {(shareLinks[doc.id] ?? []).map((link) => (
                    <div key={link.id} className="flex items-center gap-2 text-xs">
                      <input
                        readOnly
                        value={link.url}
                        className="erp-input min-w-0 flex-1 px-2 py-1 text-xs"
                        onFocus={(e) => e.target.select()}
                      />
                      <button
                        type="button"
                        onClick={() => handleCopyLink(link.url)}
                        className="shrink-0 rounded border border-border px-2 py-1 text-[#ccc] hover:bg-white/5"
                      >
                        Copy
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleRevokeShareLink(doc, link.id)}
                        disabled={isSharing}
                        className="shrink-0 text-rose-400 hover:text-rose-300 disabled:opacity-40"
                      >
                        Revoke
                      </button>
                      <span className="shrink-0 text-muted">
                        expires {new Date(link.expires_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                  {(shareLinks[doc.id]?.length ?? 0) === 0 && (
                    <p className="text-xs text-muted">No active share links.</p>
                  )}
                  <div className="flex items-center gap-2">
                    {[3, 7, 14, 30].map((days) => (
                      <button
                        key={days}
                        type="button"
                        onClick={() => void handleCreateShareLink(doc, days)}
                        disabled={isSharing}
                        className="rounded border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
                      >
                        + {days}d link
                      </button>
                    ))}
                  </div>
                </div>
              )}
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
