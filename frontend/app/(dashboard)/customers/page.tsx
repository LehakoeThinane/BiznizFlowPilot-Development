"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { useUser } from "@/contexts/UserContext";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type { Customer, CustomerListResponse, CustomerPortalAccess } from "@/types/api";

// Mirrors app/core/entitlements.py's FEATURE_TIERS["customer_portal"] +
// FULL_ACCESS_TIERS - client-facing polish layered on top of baseline
// document management every tier already has, same shape as
// document_authoring's gating in the Documents page.
const FULL_ACCESS_TIERS = new Set(["legacy", "trial", "enterprise"]);
const CUSTOMER_PORTAL_TIERS = new Set(["growth", "professional", "enterprise"]);

const PAGE_SIZE = 20;

interface CustomerEditorState {
  name: string;
  email: string;
  phone: string;
  company: string;
  notes: string;
}

const EMPTY_EDITOR: CustomerEditorState = { name: "", email: "", phone: "", company: "", notes: "" };

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-sm text-on-surface-variant">{value}</p>
    </div>
  );
}

function CustomerForm({
  editor,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
}: {
  editor: CustomerEditorState;
  onChange: (next: CustomerEditorState) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
}) {
  function update<K extends keyof CustomerEditorState>(key: K, value: CustomerEditorState[K]) {
    onChange({ ...editor, [key]: value });
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant">Name</label>
        <input
          value={editor.name}
          onChange={(e) => update("name", e.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant">Email</label>
          <input
            type="email"
            value={editor.email}
            onChange={(e) => update("email", e.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant">Phone</label>
          <input
            value={editor.phone}
            onChange={(e) => update("phone", e.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant">Company</label>
        <input
          value={editor.company}
          onChange={(e) => update("company", e.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant">Notes</label>
        <textarea
          rows={4}
          value={editor.notes}
          onChange={(e) => update("notes", e.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>
      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled}
        className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60"
      >
        {submitLabel}
      </button>
    </div>
  );
}

function ClientPortalSection({ customer, canManage }: { customer: Customer; canManage: boolean }) {
  const token = getStoredToken();
  const [status, setStatus] = useState<CustomerPortalAccess | null | undefined>(undefined);
  const [revealedUrl, setRevealedUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(() => {
    apiRequest<CustomerPortalAccess | null>(`/api/v1/customers/${customer.id}/portal-access`, { authToken: token })
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [customer.id, token]);

  useEffect(() => {
    loadStatus();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clears the previously-revealed URL on customer switch
    setRevealedUrl(null);
  }, [loadStatus]);

  if (!canManage) return null;

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<CustomerPortalAccess & { portal_url: string }>(
        `/api/v1/customers/${customer.id}/portal-access`,
        { method: "POST", authToken: token },
      );
      setRevealedUrl(result.portal_url);
      loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate portal link");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    if (!confirm("Revoke this customer's portal link? The link will stop working immediately.")) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/customers/${customer.id}/portal-access`, { method: "DELETE", authToken: token });
      setRevealedUrl(null);
      loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke portal link");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-border bg-white/5 p-4">
      <p className="text-sm font-semibold text-white">Client portal</p>
      <p className="mt-1 text-xs text-slate-400">
        A durable link this client can bookmark to view and download their own documents - stays active until you
        revoke it.
      </p>

      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}

      {revealedUrl && (
        <div className="mt-3 rounded-md border border-emerald-900/40 bg-emerald-950/30 p-3">
          <p className="text-xs text-emerald-400">Copy this link now - it won&apos;t be shown again.</p>
          <input
            readOnly
            value={revealedUrl}
            onFocus={(e) => e.target.select()}
            className="erp-input mt-1.5 w-full px-2 py-1.5 text-xs"
          />
        </div>
      )}

      {status === undefined ? (
        <p className="mt-3 text-xs text-slate-500">Loading…</p>
      ) : status ? (
        <div className="mt-3 flex items-center justify-between gap-2">
          <p className="text-xs text-slate-400">
            Link active · {status.last_accessed_at ? `last viewed ${formatDate(status.last_accessed_at)}` : "never accessed"}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={busy}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
            >
              Regenerate
            </button>
            <button
              type="button"
              onClick={() => void handleRevoke()}
              disabled={busy}
              className="rounded-md border border-red-800/40 px-3 py-1.5 text-xs text-red-400 hover:bg-red-900/20 disabled:opacity-50"
            >
              Revoke
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={busy}
          className="erp-button-primary mt-3 px-4 py-2 text-xs font-semibold disabled:opacity-60"
        >
          {busy ? "Generating…" : "Generate portal link"}
        </button>
      )}
    </div>
  );
}

export default function CustomersPage() {
  const { user } = useUser();
  const canUsePortal = !!user?.plan_tier && (FULL_ACCESS_TIERS.has(user.plan_tier) || CUSTOMER_PORTAL_TIERS.has(user.plan_tier));

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editor, setEditor] = useState<CustomerEditorState>(EMPTY_EDITOR);

  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadCustomers = useCallback(() => {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }

    setIsLoading(true);
    setError(null);
    const skip = (page - 1) * PAGE_SIZE;
    const params = new URLSearchParams({ skip: String(skip), limit: String(PAGE_SIZE) });
    if (search.trim()) params.set("name", search.trim());

    apiRequest<CustomerListResponse>(`/api/v1/customers?${params.toString()}`, { authToken: token })
      .then((d) => {
        setCustomers(d.items);
        setTotal(d.total);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
        setError(e instanceof Error ? e.message : "Unable to load customers.");
      })
      .finally(() => setIsLoading(false));
  }, [page, search]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCustomers(), 0);
    return () => window.clearTimeout(timer);
  }, [loadCustomers]);

  async function openCustomerDetails(customerId: string) {
    const token = getStoredToken();
    try {
      const customer = await apiRequest<Customer>(`/api/v1/customers/${customerId}`, { authToken: token });
      setSelectedCustomer(customer);
      setIsEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load customer.");
    }
  }

  const searchParams = useSearchParams();
  useEffect(() => {
    const openId = searchParams.get("open");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- deep-link support, mirrors leads/page.tsx
    if (openId) void openCustomerDetails(openId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function hydrateEditor(customer: Customer) {
    setEditor({
      name: customer.name,
      email: customer.email ?? "",
      phone: customer.phone ?? "",
      company: customer.company ?? "",
      notes: customer.notes ?? "",
    });
  }

  async function handleCreate() {
    if (!editor.name.trim()) { setError("Name is required."); return; }
    const token = getStoredToken();
    setIsSaving(true);
    setError(null);
    try {
      await apiRequest<Customer>("/api/v1/customers", {
        method: "POST",
        authToken: token,
        body: {
          name: editor.name.trim(),
          email: editor.email.trim() || null,
          phone: editor.phone.trim() || null,
          company: editor.company.trim() || null,
          notes: editor.notes.trim() || null,
        },
      });
      setIsCreateOpen(false);
      setEditor(EMPTY_EDITOR);
      loadCustomers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create customer.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveEdits() {
    if (!selectedCustomer) return;
    if (!editor.name.trim()) { setError("Name is required."); return; }
    const token = getStoredToken();
    setIsSaving(true);
    setError(null);
    try {
      const updated = await apiRequest<Customer>(`/api/v1/customers/${selectedCustomer.id}`, {
        method: "PATCH",
        authToken: token,
        body: {
          name: editor.name.trim(),
          email: editor.email.trim() || null,
          phone: editor.phone.trim() || null,
          company: editor.company.trim() || null,
          notes: editor.notes.trim() || null,
        },
      });
      setSelectedCustomer(updated);
      setIsEditing(false);
      loadCustomers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to update customer.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedCustomer) return;
    if (!confirm(`Delete "${selectedCustomer.name}"?`)) return;
    const token = getStoredToken();
    setIsDeleting(true);
    setError(null);
    try {
      await apiRequest<void>(`/api/v1/customers/${selectedCustomer.id}`, { method: "DELETE", authToken: token });
      setSelectedCustomer(null);
      loadCustomers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to delete customer.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Customers</h1>
          <p className="mt-1 text-sm text-muted">Your ongoing client relationships - documents, notes, activity.</p>
        </div>
        <button
          type="button"
          className="erp-button-primary px-4 py-2 text-sm font-semibold"
          onClick={() => { setEditor(EMPTY_EDITOR); setIsCreateOpen(true); setError(null); }}
        >
          Add Customer
        </button>
      </div>

      <input
        type="text"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        placeholder="Search name…"
        className="erp-input w-full max-w-sm px-3 py-2 text-sm"
      />

      {error && (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {isLoading ? (
        <div className="erp-panel p-5 text-sm text-muted">Loading customers…</div>
      ) : customers.length === 0 ? (
        <div className="erp-panel p-5 text-sm text-muted">No customers found.</div>
      ) : (
        <div className="overflow-x-auto erp-panel">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-dim text-left">
              <tr>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Name</th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Email</th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Phone</th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Company</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr
                  key={customer.id}
                  className="cursor-pointer border-t border-outline-variant/70 hover:bg-surface-container-high/70"
                  onClick={() => void openCustomerDetails(customer.id)}
                >
                  <td className="px-4 py-3 text-white">{customer.name}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{customer.email ?? "-"}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{customer.phone ?? "-"}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{customer.company ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-on-surface-variant">
        <p>Page {page} of {totalPages}</p>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-outline-variant bg-background px-3 py-1 disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-md border border-outline-variant bg-background px-3 py-1 disabled:opacity-50"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </div>

      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => setIsCreateOpen(false)}
            aria-label="Close create customer panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Add Customer</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => setIsCreateOpen(false)}
              >
                Close
              </button>
            </div>
            <CustomerForm
              editor={editor}
              onChange={setEditor}
              onSubmit={() => void handleCreate()}
              submitLabel={isSaving ? "Creating…" : "Create Customer"}
              disabled={isSaving}
            />
          </aside>
        </div>
      )}

      {selectedCustomer && (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => { setSelectedCustomer(null); setIsEditing(false); }}
            aria-label="Close customer details panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Customer Details</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => { setSelectedCustomer(null); setIsEditing(false); }}
              >
                Close
              </button>
            </div>

            {!isEditing ? (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <DetailItem label="Name" value={selectedCustomer.name} />
                  <DetailItem label="Email" value={selectedCustomer.email ?? "-"} />
                  <DetailItem label="Phone" value={selectedCustomer.phone ?? "-"} />
                  <DetailItem label="Company" value={selectedCustomer.company ?? "-"} />
                  <DetailItem label="Created" value={formatDate(selectedCustomer.created_at)} />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Notes</p>
                  <p className="mt-1 rounded-md border border-border bg-white/5 p-3 text-sm text-on-surface-variant whitespace-pre-wrap">
                    {selectedCustomer.notes?.trim() || "No notes"}
                  </p>
                </div>

                <ActivityTimeline entityType="customer" entityId={selectedCustomer.id} />

                <ClientPortalSection customer={selectedCustomer} canManage={canUsePortal} />

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="erp-button-primary px-4 py-2 text-sm font-semibold"
                    onClick={() => { hydrateEditor(selectedCustomer); setIsEditing(true); }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                    disabled={isDeleting}
                    onClick={() => void handleDelete()}
                  >
                    {isDeleting ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <CustomerForm
                  editor={editor}
                  onChange={setEditor}
                  onSubmit={() => void handleSaveEdits()}
                  submitLabel={isSaving ? "Saving…" : "Save"}
                  disabled={isSaving}
                />
                <button
                  type="button"
                  className="rounded-md border border-border px-4 py-2 text-sm text-on-surface-variant hover:bg-white/5"
                  onClick={() => { hydrateEditor(selectedCustomer); setIsEditing(false); }}
                >
                  Cancel
                </button>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
