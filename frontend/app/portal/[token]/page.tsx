"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { apiRequest } from "@/lib/api";
import type { CustomerPortalDetail, CustomerPortalDownload } from "@/types/api";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function CustomerPortalPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [detail, setDetail] = useState<CustomerPortalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<CustomerPortalDetail>(`/api/v1/portal/${token}`)
      .then(setDetail)
      .catch(() => setInvalid(true))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleDownload(documentId: string) {
    setBusyDocId(documentId);
    try {
      const { url } = await apiRequest<CustomerPortalDownload>(
        `/api/v1/portal/${token}/documents/${documentId}/download-url`,
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      // no-op - the link itself will show as unusable if the token was revoked mid-session
    } finally {
      setBusyDocId(null);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0e17] px-4 py-12">
      <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#12172a] p-6">
        {loading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : invalid || !detail ? (
          <p className="text-sm text-slate-400">This link is invalid or has been revoked.</p>
        ) : (
          <>
            <p className="text-xs uppercase tracking-wide text-slate-500">Documents from</p>
            <h1 className="mt-1 text-xl font-semibold text-white">{detail.business_name}</h1>
            <p className="mt-1 text-sm text-slate-400">Shared with {detail.customer_name}</p>

            <div className="mt-6 divide-y divide-white/5 rounded-xl border border-white/10">
              {detail.documents.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-slate-500">No documents shared yet.</p>
              ) : (
                detail.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm text-white">{doc.filename}</p>
                      <p className="text-xs text-slate-500">{formatSize(doc.size_bytes)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleDownload(doc.id)}
                      disabled={busyDocId === doc.id}
                      className="shrink-0 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
                    >
                      Download
                    </button>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
