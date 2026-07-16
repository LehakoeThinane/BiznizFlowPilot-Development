"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { apiRequest, ApiError } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { AppTileIcon } from "@/components/AppTileIcon";
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

const ACCENTS = [
  "bg-blue-500/20 text-blue-300",
  "bg-violet-500/20 text-violet-300",
  "bg-emerald-500/20 text-emerald-300",
  "bg-orange-500/20 text-orange-300",
  "bg-teal-500/20 text-teal-300",
  "bg-yellow-500/20 text-yellow-300",
];

function accentFor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) % ACCENTS.length;
  return ACCENTS[hash];
}

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

function FolderCard({ folder, onOpen }: { folder: BusinessFolder; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group erp-panel flex h-full flex-col p-5 text-left transition-all hover:-translate-y-0.5 hover:border-primary-fixed-dim/50"
    >
      <div className="flex items-start justify-between">
        <div className={`glow-badge flex h-11 w-11 items-center justify-center ${accentFor(folder.id)}`}>
          <AppTileIcon name="folder" className="h-6 w-6" />
        </div>
        <span className="rounded-full border border-tertiary-fixed-dim/20 bg-tertiary-fixed-dim/10 px-2 py-0.5 text-[10px] font-bold text-tertiary-fixed-dim">
          FOLDER
        </span>
      </div>
      <p className="mt-4 truncate text-[15px] font-semibold text-surface-bright">{folder.name}</p>
      <p className="mt-1.5 flex-1 text-[13px] text-on-surface-variant">Created {formatDate(folder.created_at)}</p>
      <span className="erp-button-primary mt-5 flex w-full items-center justify-center py-2 text-sm font-semibold">
        Open
      </span>
    </button>
  );
}

function NewFolderCard({
  isCreating,
  name,
  onNameChange,
  onStart,
  onCreate,
  onCancel,
}: {
  isCreating: boolean;
  name: string;
  onNameChange: (v: string) => void;
  onStart: () => void;
  onCreate: () => void;
  onCancel: () => void;
}) {
  if (isCreating) {
    return (
      <div className="erp-panel flex h-full flex-col justify-center gap-2 p-5">
        <input
          autoFocus
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onCreate()}
          placeholder="Folder name…"
          className="erp-input px-3 py-2 text-sm"
        />
        <div className="flex gap-2">
          <button type="button" onClick={onCreate} className="erp-button-primary flex-1 py-2 text-sm font-semibold">
            Create
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border px-3 py-2 text-sm text-[#ccc] hover:bg-white/5"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={onStart}
      className="flex h-full min-h-[172px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border p-5 text-on-surface-variant transition-colors hover:border-primary-fixed-dim/50 hover:text-surface-bright"
    >
      <span className="text-2xl leading-none">+</span>
      <span className="text-sm font-medium">New folder</span>
    </button>
  );
}

function DocumentRow({
  doc,
  inFolder,
  busyDocId,
  onDownload,
  onDelete,
}: {
  doc: BusinessDocument;
  inFolder: boolean;
  busyDocId: string | null;
  onDownload: (doc: BusinessDocument) => void;
  onDelete: (doc: BusinessDocument, inFolder: boolean) => void;
}) {
  return (
    <tr className="border-t border-white/5 hover:bg-white/[0.02]">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2.5">
          <AppTileIcon name="description" className="h-4 w-4 shrink-0 text-on-surface-variant" />
          <button
            type="button"
            onClick={() => onDownload(doc)}
            disabled={!doc.has_access || busyDocId === doc.id}
            className="text-left text-[#ddd] hover:text-white hover:underline disabled:opacity-40"
          >
            {doc.restricted ? "🔒 " : ""}{doc.filename}
          </button>
          {doc.version > 1 && <span className="text-xs text-muted">v{doc.version}</span>}
        </div>
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
          onClick={() => onDelete(doc, inFolder)}
          disabled={busyDocId === doc.id}
          className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
        >
          Delete
        </button>
      </td>
    </tr>
  );
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
    const folderId = currentFolder?.id;
    const timer = window.setTimeout(() => {
      if (folderId) {
        loadFolderContents(folderId);
      } else {
        loadFlat();
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [currentFolder, loadFlat, loadFolderContents]);

  function openFolder(folder: BusinessFolder) {
    setFolderPath((prev) => [...prev, folder]);
  }

  function navigateToBreadcrumb(index: number) {
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

  return (
    <div className="-m-6 min-h-[calc(100vh-3rem)] px-8 py-8">
      {currentFolder ? (
        <>
          {/* Breadcrumb */}
          <div className="mb-6 flex items-center justify-between">
            <div className="flex flex-wrap items-center gap-1 text-sm text-on-surface-variant">
              <button type="button" onClick={() => navigateToBreadcrumb(-1)} className="hover:text-surface-bright hover:underline">
                Documents
              </button>
              {folderPath.map((f, i) => (
                <span key={f.id} className="flex items-center gap-1">
                  <span className="text-muted">/</span>
                  <button type="button" onClick={() => navigateToBreadcrumb(i)} className="hover:text-surface-bright hover:underline">
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
                className="erp-button-primary px-3 py-2 text-sm font-semibold disabled:opacity-40"
              >
                {isUploadingToFolder ? "Uploading…" : "+ Upload file"}
              </button>
              <input
                ref={folderFileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.svg,.csv,.txt,.zip"
                className="hidden"
                onChange={(e) => void handleUploadToFolder(e.target.files?.[0])}
              />
            </div>
          </div>

          <h1 className="text-[28px] font-bold leading-tight tracking-tight text-surface-bright">{currentFolder.name}</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            {folderChildren.length} folder{folderChildren.length === 1 ? "" : "s"} · {folderDocuments.length} document
            {folderDocuments.length === 1 ? "" : "s"}
          </p>

          {error && (
            <div className="mt-4 rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">{error}</div>
          )}

          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {folderChildren.map((f) => (
              <FolderCard key={f.id} folder={f} onOpen={() => openFolder(f)} />
            ))}
            <NewFolderCard
              isCreating={isCreatingFolder}
              name={newFolderName}
              onNameChange={setNewFolderName}
              onStart={() => setIsCreatingFolder(true)}
              onCreate={() => void handleCreateFolder()}
              onCancel={() => { setIsCreatingFolder(false); setNewFolderName(""); }}
            />
          </div>

          <div className="mt-8 erp-panel overflow-hidden">
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
                <tbody>
                  {folderDocuments.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      doc={doc}
                      inFolder
                      busyDocId={busyDocId}
                      onDownload={handleDownload}
                      onDelete={handleDelete}
                    />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : (
        <>
          <h1 className="text-[32px] font-bold leading-tight tracking-tight text-surface-bright">Documents</h1>
          <p className="mt-1 text-sm text-on-surface-variant">Organize files by folder, or browse everything attached to a record</p>

          <p className="mb-5 mt-10 text-[11px] font-semibold tracking-widest text-on-surface-variant">FOLDERS</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {topLevelFolders.map((f) => (
              <FolderCard key={f.id} folder={f} onOpen={() => openFolder(f)} />
            ))}
            <NewFolderCard
              isCreating={isCreatingFolder}
              name={newFolderName}
              onNameChange={setNewFolderName}
              onStart={() => setIsCreatingFolder(true)}
              onCreate={() => void handleCreateFolder()}
              onCancel={() => { setIsCreatingFolder(false); setNewFolderName(""); }}
            />
          </div>

          <div className="mb-5 mt-10 flex items-center justify-between">
            <p className="text-[11px] font-semibold tracking-widest text-on-surface-variant">ALL DOCUMENTS</p>
            <div className="flex items-center gap-2">
              <input
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="Search filename…"
                className="erp-input px-3 py-2 text-sm"
              />
              <select
                aria-label="Filter by record type"
                value={entityFilter}
                onChange={(e) => { setEntityFilter(e.target.value); setPage(1); }}
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
                <tbody>
                  {documents.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      doc={doc}
                      inFolder={false}
                      busyDocId={busyDocId}
                      onDownload={handleDownload}
                      onDelete={handleDelete}
                    />
                  ))}
                </tbody>
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
  );
}
