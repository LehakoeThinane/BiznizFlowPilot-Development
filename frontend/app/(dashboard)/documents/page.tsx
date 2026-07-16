"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Pagination } from "@/components/Pagination";
import type { BusinessDocument, DocumentDownloadResponse, DocumentListResponse } from "@/types/api";

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
  const [documents, setDocuments] = useState<BusinessDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entityFilter, setEntityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [busyDocId, setBusyDocId] = useState<string | null>(null);

  const token = getStoredToken();

  const load = useCallback(() => {
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

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [entityFilter, search]);

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

  async function handleDelete(doc: BusinessDocument) {
    if (!confirm(`Delete "${doc.filename}"?`)) return;
    setBusyDocId(doc.id);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/documents/${doc.id}`, { method: "DELETE", authToken: token });
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
      setTotal((prev) => prev - 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete file");
    } finally {
      setBusyDocId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
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
            <tbody>
              {documents.map((doc) => (
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
                  <td className="px-4 py-3">
                    <Link href={entityHref(doc.entity_type, doc.entity_id)} className="text-[#8ab4f8] hover:underline">
                      {entityLabel(doc.entity_type)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatSize(doc.size_bytes)}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDate(doc.created_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void handleDelete(doc)}
                      disabled={busyDocId === doc.id}
                      className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
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
    </div>
  );
}
