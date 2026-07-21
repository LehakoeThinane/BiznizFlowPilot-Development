"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { InventorySubNav } from "@/components/InventorySubNav";
import type { Supplier, SupplierListResponse } from "@/types/api";

type SortField = "name" | "code" | "email" | "rating" | "created";
type SortDirection = "asc" | "desc";

interface Editor {
  name: string;
  code: string;
  email: string;
  phone: string;
  website: string;
  payment_terms: string;
  rating: string;
  notes: string;
  is_active: boolean;
}

const EMPTY_EDITOR: Editor = {
  name: "",
  code: "",
  email: "",
  phone: "",
  website: "",
  payment_terms: "",
  rating: "",
  notes: "",
  is_active: true,
};

const PAGE_SIZE = 20;

function formatDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function toErrorMessage(err: unknown, fallback: string) {
  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}

function ratingStars(rating: number | null) {
  if (!rating) return "-";
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">("all");
  const [sortField, setSortField] = useState<SortField>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editor, setEditor] = useState<Editor>(EMPTY_EDITOR);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = suppliers.filter((s) => {
      if (activeFilter === "active" && !s.is_active) return false;
      if (activeFilter === "inactive" && s.is_active) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || (s.code ?? "").toLowerCase().includes(q) || (s.email ?? "").toLowerCase().includes(q);
    });
    filtered.sort((a, b) => {
      if (sortField === "name") return a.name.localeCompare(b.name);
      if (sortField === "code") return (a.code ?? "").localeCompare(b.code ?? "");
      if (sortField === "email") return (a.email ?? "").localeCompare(b.email ?? "");
      if (sortField === "rating") return (a.rating ?? 0) - (b.rating ?? 0);
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    });
    if (sortDirection === "desc") filtered.reverse();
    return filtered;
  }, [suppliers, search, activeFilter, sortField, sortDirection]);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsLoading(true);
    setError(null);
    const skip = (page - 1) * PAGE_SIZE;
    try {
      const res = await apiRequest<SupplierListResponse>(
        `/api/v1/suppliers?skip=${skip}&limit=${PAGE_SIZE}`,
        { method: "GET", authToken: token },
      );
      setSuppliers(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to load suppliers."));
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => {
    const t = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(t);
  }, [load]);

  function handleSort(field: SortField) {
    setSortField((prev) => {
      if (prev === field) { setSortDirection((d) => d === "asc" ? "desc" : "asc"); return prev; }
      setSortDirection(field === "created" ? "desc" : "asc");
      return field;
    });
  }

  function hydrateEditor(s: Supplier) {
    setEditor({
      name: s.name,
      code: s.code ?? "",
      email: s.email ?? "",
      phone: s.phone ?? "",
      website: s.website ?? "",
      payment_terms: s.payment_terms ?? "",
      rating: s.rating !== null ? String(s.rating) : "",
      notes: s.notes ?? "",
      is_active: s.is_active,
    });
  }

  async function handleCreate() {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    if (!editor.name.trim()) { setError("Supplier name is required."); return; }
    setIsSavingCreate(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<Supplier>("/api/v1/suppliers", {
        method: "POST",
        authToken: token,
        body: {
          name: editor.name.trim(),
          code: editor.code.trim() || null,
          email: editor.email.trim() || null,
          phone: editor.phone.trim() || null,
          website: editor.website.trim() || null,
          payment_terms: editor.payment_terms.trim() || null,
          rating: editor.rating ? parseInt(editor.rating, 10) : null,
          notes: editor.notes.trim() || null,
          is_active: editor.is_active,
          meta_data: {},
        },
      });
      setIsCreateOpen(false);
      setEditor(EMPTY_EDITOR);
      setSuccessMessage("Supplier created.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to create supplier."));
    } finally {
      setIsSavingCreate(false);
    }
  }

  async function handleSaveEdit() {
    if (!selectedSupplier) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsSavingEdit(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiRequest<Supplier>(`/api/v1/suppliers/${selectedSupplier.id}`, {
        method: "PATCH",
        authToken: token,
        body: {
          name: editor.name.trim() || undefined,
          code: editor.code.trim() || null,
          email: editor.email.trim() || null,
          phone: editor.phone.trim() || null,
          website: editor.website.trim() || null,
          payment_terms: editor.payment_terms.trim() || null,
          rating: editor.rating ? parseInt(editor.rating, 10) : null,
          notes: editor.notes.trim() || null,
          is_active: editor.is_active,
        },
      });
      setSelectedSupplier(updated);
      setIsEditing(false);
      setSuccessMessage("Supplier updated.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to update supplier."));
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleDelete() {
    if (!selectedSupplier) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<{ message: string }>(`/api/v1/suppliers/${selectedSupplier.id}`, { method: "DELETE", authToken: token });
      setSelectedSupplier(null);
      setIsEditing(false);
      setSuccessMessage("Supplier deleted.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to delete supplier."));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="space-y-5">
      <InventorySubNav />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Suppliers</h1>
          <p className="mt-1 text-sm text-muted">Manage vendors and purchasing suppliers.</p>
        </div>
        <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
          onClick={() => { setEditor(EMPTY_EDITOR); setIsCreateOpen(true); setError(null); }}>
          Add Supplier
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, code, or email"
          className="min-w-[240px] rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
          className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm">
          <option value="all">All suppliers</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
        <button type="button" className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5" onClick={() => void load()}>Refresh</button>
        <button type="button" className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5"
          onClick={() => { setSearch(""); setActiveFilter("all"); setSortField("created"); setSortDirection("desc"); }}>Clear</button>
      </div>

      <p className="text-sm text-muted">Showing {visible.length} of {suppliers.length} supplier{suppliers.length === 1 ? "" : "s"}.</p>

      {successMessage && <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">{successMessage}</div>}
      {error && (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button type="button" className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium text-red-400 hover:bg-red-900/20" onClick={() => void load()}>Retry</button>
        </div>
      )}

      {isLoading ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">Loading suppliers...</div>
      ) : visible.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">No suppliers found for the current filters.</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="min-w-full text-sm">
            <thead className="bg-[#1a1a1a] text-left">
              <tr>
                {([["name", "Name"], ["code", "Code"], ["email", "Email"], ["rating", "Rating"], ["created", "Created"]] as [SortField, string][]).map(([f, label]) => (
                  <th key={f} className="px-4 py-3 font-medium text-[#aaa]">
                    <button type="button" className="inline-flex items-center gap-1 hover:text-white" onClick={() => handleSort(f)}>
                      {label}<SortIndicator active={sortField === f} direction={sortDirection} />
                    </button>
                  </th>
                ))}
                <th className="px-4 py-3 font-medium text-[#aaa]">Phone</th>
                <th className="px-4 py-3 font-medium text-[#aaa]">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr key={s.id} className="cursor-pointer border-t border-border hover:bg-white/[0.02]"
                  onClick={() => { setSelectedSupplier(s); setIsEditing(false); hydrateEditor(s); }}>
                  <td className="px-4 py-3 font-medium text-white">{s.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-[#aaa]">{s.code ?? "-"}</td>
                  <td className="px-4 py-3 text-[#aaa]">{s.email ?? "-"}</td>
                  <td className="px-4 py-3 text-amber-500">{ratingStars(s.rating)}</td>
                  <td className="px-4 py-3 text-[#aaa]">{formatDate(s.created_at)}</td>
                  <td className="px-4 py-3 text-[#aaa]">{s.phone ?? "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${s.is_active ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-[#aaa]"}`}>
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-[#aaa]">
        <p>Page {page} of {totalPages}</p>
        <div className="flex gap-2">
          <button type="button" className="rounded-md border border-border px-3 py-1 disabled:opacity-50" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <button type="button" className="rounded-md border border-border px-3 py-1 disabled:opacity-50" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      </div>

      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => setIsCreateOpen(false)} aria-label="Close" />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-[#141414] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Add Supplier</h2>
              <button type="button" className="rounded-md border border-border px-3 py-1 text-sm text-[#aaa] hover:bg-white/5" onClick={() => setIsCreateOpen(false)}>Close</button>
            </div>
            <SupplierForm editor={editor} onChange={setEditor} onSubmit={() => void handleCreate()} submitLabel={isSavingCreate ? "Creating..." : "Create Supplier"} disabled={isSavingCreate} />
          </aside>
        </div>
      )}

      {selectedSupplier && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => { setSelectedSupplier(null); setIsEditing(false); }} aria-label="Close" />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-[#141414] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Supplier Details</h2>
              <button type="button" className="rounded-md border border-border px-3 py-1 text-sm text-[#aaa] hover:bg-white/5" onClick={() => { setSelectedSupplier(null); setIsEditing(false); }}>Close</button>
            </div>
            {!isEditing ? (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <DetailItem label="Name" value={selectedSupplier.name} />
                  <DetailItem label="Code" value={selectedSupplier.code ?? "-"} />
                  <DetailItem label="Email" value={selectedSupplier.email ?? "-"} />
                  <DetailItem label="Phone" value={selectedSupplier.phone ?? "-"} />
                  <DetailItem label="Website" value={selectedSupplier.website ?? "-"} />
                  <DetailItem label="Payment Terms" value={selectedSupplier.payment_terms ?? "-"} />
                  <DetailItem label="Rating" value={ratingStars(selectedSupplier.rating)} />
                  <DetailItem label="Status" value={selectedSupplier.is_active ? "Active" : "Inactive"} />
                  <DetailItem label="Created" value={formatDate(selectedSupplier.created_at)} />
                </div>
                {selectedSupplier.notes && (
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Notes</p>
                    <p className="mt-1 rounded-md border border-border bg-white/5 p-3 text-sm text-[#ccc] whitespace-pre-wrap">{selectedSupplier.notes}</p>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
                    onClick={() => { hydrateEditor(selectedSupplier); setIsEditing(true); }}>Edit</button>
                  <button type="button" className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                    disabled={isDeleting} onClick={() => void handleDelete()}>
                    {isDeleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <SupplierForm editor={editor} onChange={setEditor} onSubmit={() => void handleSaveEdit()} submitLabel={isSavingEdit ? "Saving..." : "Save"} disabled={isSavingEdit} />
                <button type="button" className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
                  onClick={() => { hydrateEditor(selectedSupplier); setIsEditing(false); }}>Cancel</button>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

function SortIndicator({ active, direction }: { active: boolean; direction: SortDirection }) {
  if (!active) return <span className="text-[#555]">↕</span>;
  return <span>{direction === "asc" ? "↑" : "↓"}</span>;
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-sm text-[#ccc]">{value}</p>
    </div>
  );
}

function SupplierForm({ editor, onChange, onSubmit, submitLabel, disabled }: {
  editor: Editor;
  onChange: (e: Editor) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
}) {
  function set<K extends keyof Editor>(key: K, value: Editor[K]) { onChange({ ...editor, [key]: value }); }
  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-name">Name *</label>
        <input id="s-name" value={editor.name} onChange={(e) => set("name", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-code">Code</label>
          <input id="s-code" value={editor.code} onChange={(e) => set("code", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-email">Email</label>
          <input id="s-email" type="email" value={editor.email} onChange={(e) => set("email", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-phone">Phone</label>
          <input id="s-phone" value={editor.phone} onChange={(e) => set("phone", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-website">Website</label>
          <input id="s-website" value={editor.website} onChange={(e) => set("website", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-terms">Payment Terms</label>
          <input id="s-terms" value={editor.payment_terms} onChange={(e) => set("payment_terms", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-rating">Rating (1–5)</label>
          <input id="s-rating" type="number" min="1" max="5" value={editor.rating} onChange={(e) => set("rating", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="s-notes">Notes</label>
        <textarea id="s-notes" rows={3} value={editor.notes} onChange={(e) => set("notes", e.target.value)} className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm" />
      </div>
      <label className="flex items-center gap-2 text-sm text-[#aaa] cursor-pointer">
        <input type="checkbox" checked={editor.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Active
      </label>
      <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" onClick={onSubmit} disabled={disabled}>
        {submitLabel}
      </button>
    </div>
  );
}
