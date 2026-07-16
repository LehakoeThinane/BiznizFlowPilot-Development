"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { apiRequest, ApiError } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { Pagination } from "@/components/Pagination";
import type {
  BusinessDocument,
  BusinessFolder,
  DocumentDownloadResponse,
  DocumentListResponse,
  FolderListResponse,
} from "@/types/api";

const PAGE_SIZE = 25;

const ENTITY_TYPES = ["", "lead", "task"];

function entityLabel(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function entityHref(type: string, id: string): string {
  if (type === "lead") return `/leads?open=${id}`;
  if (type === "task") return `/tasks?open=${id}`;
  return "#";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function DocumentLibraryPage() {
  // Flat "All Documents" view
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [entityFilter, setEntityFilter] = useState("");
  const [search, setSearch] = useState("");

  // Folder browsing
  const [folderPath, setFolderPath] = useState<BusinessFolder[]>([]);
  const [folderChildren, setFolderChildren] = useState<BusinessFolder[]>([]);
  const [topLevelFolders, setTopLevelFolders] = useState<BusinessFolder[]>([]);
  const [folderDocuments, setFolderDocuments] = useState<BusinessDocument[]>([]);
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isUploadingToFolder, setIsUploadingToFolder] = useState(false);
  const folderFileInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);

  const token = getStoredToken();
  const currentFolder = folderPath[folderPath.length - 1] ?? null;

  const loadTopLevelFolders = useCallback(() => {
    apiRequest<FolderListResponse>("/api/v1/folders", { authToken: token })
      .then((d) => setTopLevelFolders(d.items ?? []))
      .catch(() => setTopLevelFolders([]));
  }, [token]);

  const loadFlat = useCallback(() => {
    setLoading(true);
    setError(null);
    const skip = (page - 1) * PAGE_SIZE;
    const params = new URLSearchParams({ skip: String(skip), limit: String(PAGE_SIZE) });
    if (entityFilter) params.set("entity_type", entityFilter);
    if (search.trim()) params.set("search", search.trim());

    apiRequest<DocumentListResponse>(`/api/v1/documents/library?${params.toString()}`, { authToken: token })
      .then((d) => {
        setDocuments(d.items ?? []);
        setTotal(d.total ?? 0);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) {
          logout();
          window.location.replace("/login");
          return;
        }
        setDocuments([]);
        setTotal(0);
        setError(e instanceof Error ? e.message : "Failed to load documents");
      })
      .finally(() => setLoading(false));
  }, [token, page, entityFilter, search]);

  const loadFolderContents = useCallback(
    (folderId: string) => {
      setLoading(true);
      setError(null);
      Promise.all([
        apiRequest<FolderListResponse>(`/api/v1/folders?parent_folder_id=${folderId}`, { authToken: token }),
        apiRequest<DocumentListResponse>(
          `/api/v1/documents?entity_type=folder&entity_id=${folderId}`,
          { authToken: token },
        ),
      ])
        .then(([foldersResp, docsResp]) => {
          setFolderChildren(foldersResp.items ?? []);
          setFolderDocuments(docsResp.items ?? []);
        })
        .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load folder"))
        .finally(() => setLoading(false));
    },
    [token],
  );

  useEffect(() => {
    loadTopLevelFolders();
  }, [loadTopLevelFolders]);

  useEffect(() => {
    if (currentFolder) {
      loadFolderContents(currentFolder.id);
    } else {
      const timer = window.setTimeout(loadFlat, 0);
      return () => window.clearTimeout(timer);
    }
  }, [currentFolder, loadFlat, loadFolderContents]);

  useEffect(() => {
    setPage(1);
  }, [entityFilter, search]);

  function openFolder(folder: BusinessFolder) {
    setFolderPath((prev) => [...prev, folder]);
  }

  function navigateToBreadcrumb(index: number) {
    // index === -1 means "Home" (root, no folder)
    setFolderPath((prev) => prev.slice(0, index + 1));
  }

  async function handleCreateFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    setError(null);
    try {
      await apiRequest<BusinessFolder>("/api/v1/folders", {
        method: "POST",
        authToken: token,
        body: { name, parent_folder_id: currentFolder?.id ?? null },
      });
      setNewFolderName("");
      setIsCreatingFolder(false);
      if (currentFolder) {
        loadFolderContents(currentFolder.id);
      } else {
        loadTopLevelFolders();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create folder");
    }
  }

  async function handleUploadToFolder(file: File | undefined) {
    if (!file || !currentFolder) return;
    setIsUploadingToFolder(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("entity_type", "folder");
      formData.append("entity_id", currentFolder.id);
      formData.append("file", file);
      await apiRequest<BusinessDocument>("/api/v1/documents", { method: "POST", authToken: token, body: formData });
      loadFolderContents(currentFolder.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload file");
    } finally {
      setIsUploadingToFolder(false);
      if (folderFileInputRef.current) folderFileInputRef.current.value = "";
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

  async function handleDelete(doc: BusinessDocument, inFolder: boolean) {
    if (!confirm(`Delete "${doc.filename}"?`)) return;
    setBusyDocId(doc.id);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/documents/${doc.id}`, { method: "DELETE", authToken: token });
      if (inFolder) {
        setFolderDocuments((prev) => prev.filter((d) => d.id !== doc.id));
      } else {
        setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
        setTotal((prev) => prev - 1);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete file");
    } finally {
      setBusyDocId(null);
    }
  }

  function renderDocumentRow(doc: BusinessDocument, inFolder: boolean) {
    return (
      <tr key={doc.id} className="border-t border-white/5 hover:bg-white/[0.02]">
        <td className="px-4 py-3">
          <button
            type="button"
            onClick={() => void handleDownload(doc)}
            disabled={!doc.has_access || busyDocId === doc.id}
            className="text-left text-[#ddd] hover:text-white hover:underline disabled:opacity-40"
          >
            {doc.restricted ? "🔒 " : ""}{doc.filename}
          </button>
          {doc.version > 1 && <span className="ml-2 text-xs text-muted">v{doc.version}</span>}
        </td>
        {!inFolder && (
          <td className="px-4 py-3">
            <Link href={entityHref(doc.entity_type, doc.entity_id)} className="text-[#8ab4f8] hover:underline">
              {entityLabel(doc.entity_type)}
            </Link>
          </td>
        )}
        <td className="px-4 py-3 text-slate-400">{formatSize(doc.size_bytes)}</td>
        <td className="px-4 py-3 text-slate-400">{formatDate(doc.created_at)}</td>
        <td className="px-4 py-3">
          <button
            type="button"
            onClick={() => void handleDelete(doc, inFolder)}
            disabled={busyDocId === doc.id}
            className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
          >
            Delete
          </button>
        </td>
      </tr>
    );
  }

  return (
    <div className="flex gap-6 p-6">
      {/* ── Folder sidebar ─────────────────────────────────────────────── */}
      <aside className="w-56 shrink-0">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Folders</p>
        <button
          type="button"
          onClick={() => setFolderPath([])}
          className={`mb-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm ${
            !currentFolder ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5"
          }`}
        >
          📁 All Documents
        </button>
        {topLevelFolders.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFolderPath([f])}
            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm ${
              currentFolder?.id === f.id ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5"
            }`}
          >
            📂 {f.name}
          </button>
        ))}
      </aside>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-4">
        {currentFolder ? (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 text-sm text-slate-400">
                <button type="button" onClick={() => navigateToBreadcrumb(-1)} className="hover:text-white hover:underline">
                  Home
                </button>
                {folderPath.map((f, i) => (
                  <span key={f.id} className="flex items-center gap-1">
                    <span>/</span>
                    <button type="button" onClick={() => navigateToBreadcrumb(i)} className="hover:text-white hover:underline">
                      {f.name}
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => folderFileInputRef.current?.click()}
                  disabled={isUploadingToFolder}
                  className="rounded-md border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5 disabled:opacity-40"
                >
                  {isUploadingToFolder ? "Uploading…" : "+ Upload here"}
                </button>
                <input
                  ref={folderFileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.svg,.csv,.txt,.zip"
                  className="hidden"
                  onChange={(e) => void handleUploadToFolder(e.target.files?.[0])}
                />
                <button
                  type="button"
                  onClick={() => setIsCreatingFolder((v) => !v)}
                  className="rounded-md border border-border px-2 py-1 text-xs text-[#ccc] hover:bg-white/5"
                >
                  + New folder
                </button>
              </div>
            </div>

            {isCreatingFolder && (
              <div className="flex items-center gap-2">
                <input
                  autoFocus
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void handleCreateFolder()}
                  placeholder="Folder name…"
                  className="erp-input px-3 py-2 text-sm"
                />
                <button type="button" onClick={() => void handleCreateFolder()} className="erp-button-primary px-3 py-2 text-sm">
                  Create
                </button>
              </div>
            )}

            {error && (
              <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">{error}</div>
            )}

            {folderChildren.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {folderChildren.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => openFolder(f)}
                    className="erp-panel flex items-center gap-2 px-4 py-3 text-sm text-[#ddd] hover:text-white"
                  >
                    📂 {f.name}
                  </button>
                ))}
              </div>
            )}

            <div className="erp-panel overflow-hidden">
              {loading ? (
                <div className="px-5 py-10 text-sm text-slate-400">Loading…</div>
              ) : folderDocuments.length === 0 ? (
                <div className="px-5 py-10 text-center text-sm text-slate-500">No documents in this folder yet.</div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-[11px] uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Filename</th>
                      <th className="px-4 py-3">Size</th>
                      <th className="px-4 py-3">Uploaded</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>{folderDocuments.map((doc) => renderDocumentRow(doc, true))}</tbody>
                </table>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-bold text-white">Documents</h1>
                <p className="mt-1 text-xs text-slate-400">Every file attached across the business — {total} total</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search filename…"
                  className="erp-input px-3 py-2 text-sm"
                />
                <select
                  aria-label="Filter by record type"
                  value={entityFilter}
                  onChange={(e) => setEntityFilter(e.target.value)}
                  className="erp-input px-3 py-2 text-sm"
                >
                  <option value="">All records</option>
                  {ENTITY_TYPES.filter(Boolean).map((t) => (
                    <option key={t} value={t}>{entityLabel(t)}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="erp-panel overflow-hidden">
              {error && (
                <div className="border-b border-red-900/40 bg-red-950/30 px-5 py-3 text-sm text-red-400">{error}</div>
              )}
              {loading ? (
                <div className="px-5 py-10 text-sm text-slate-400">Loading…</div>
              ) : documents.length === 0 ? (
                <div className="px-5 py-10 text-center text-sm text-slate-500">
                  {error ? "Unable to load documents right now." : "No documents found."}
                </div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-[11px] uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Filename</th>
                      <th className="px-4 py-3">Attached to</th>
                      <th className="px-4 py-3">Size</th>
                      <th className="px-4 py-3">Uploaded</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>{documents.map((doc) => renderDocumentRow(doc, false))}</tbody>
                </table>
              )}
              <Pagination
                page={page}
                totalPages={Math.max(1, Math.ceil(total / PAGE_SIZE))}
                totalItems={total}
                pageSize={PAGE_SIZE}
                onPrev={() => setPage((p) => p - 1)}
                onNext={() => setPage((p) => p + 1)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
