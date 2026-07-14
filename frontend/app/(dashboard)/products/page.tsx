"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import type { Product, ProductListResponse, ProductType } from "@/types/api";

type SortField = "name" | "sku" | "category" | "price" | "created";
type SortDirection = "asc" | "desc";

interface Editor {
  sku: string;
  name: string;
  description: string;
  product_type: ProductType;
  category: string;
  unit_price: string;
  cost_price: string;
  is_active: boolean;
  track_inventory: boolean;
}

const EMPTY_EDITOR: Editor = {
  sku: "",
  name: "",
  description: "",
  product_type: "physical",
  category: "",
  unit_price: "",
  cost_price: "",
  is_active: true,
  track_inventory: true,
};

const PAGE_SIZE = 20;

function statusBadge(active: boolean) {
  return active ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-on-surface-variant";
}

function formatDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function fmt(amount: string): string {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(parseFloat(amount));
}

function toErrorMessage(err: unknown, fallback: string) {
  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
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
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editor, setEditor] = useState<Editor>(EMPTY_EDITOR);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = products.filter((p) => {
      if (activeFilter === "active" && !p.is_active) return false;
      if (activeFilter === "inactive" && p.is_active) return false;
      if (!q) return true;
      return p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || (p.category ?? "").toLowerCase().includes(q);
    });

    filtered.sort((a, b) => {
      if (sortField === "name") return a.name.localeCompare(b.name);
      if (sortField === "sku") return a.sku.localeCompare(b.sku);
      if (sortField === "category") return (a.category ?? "").localeCompare(b.category ?? "");
      if (sortField === "price") return parseFloat(a.unit_price) - parseFloat(b.unit_price);
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    });
    if (sortDirection === "desc") filtered.reverse();
    return filtered;
  }, [products, search, activeFilter, sortField, sortDirection]);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsLoading(true);
    setError(null);
    const skip = (page - 1) * PAGE_SIZE;
    try {
      const res = await apiRequest<ProductListResponse>(
        `/api/v1/products?skip=${skip}&limit=${PAGE_SIZE}`,
        { method: "GET", authToken: token },
      );
      setProducts(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to load products."));
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

  function hydrateEditor(p: Product) {
    setEditor({
      sku: p.sku,
      name: p.name,
      description: p.description ?? "",
      product_type: p.product_type,
      category: p.category ?? "",
      unit_price: p.unit_price,
      cost_price: p.cost_price ?? "",
      is_active: p.is_active,
      track_inventory: p.track_inventory,
    });
  }

  async function handleCreate() {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    if (!editor.sku.trim() || !editor.name.trim() || !editor.unit_price.trim()) {
      setError("SKU, name, and unit price are required.");
      return;
    }
    setIsSavingCreate(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<Product>("/api/v1/products", {
        method: "POST",
        authToken: token,
        body: {
          sku: editor.sku.trim(),
          name: editor.name.trim(),
          description: editor.description.trim() || null,
          product_type: editor.product_type,
          category: editor.category.trim() || null,
          unit_price: parseFloat(editor.unit_price),
          cost_price: editor.cost_price.trim() ? parseFloat(editor.cost_price) : null,
          is_active: editor.is_active,
          track_inventory: editor.track_inventory,
          tax_rate: 0,
          weight_unit: "kg",
          meta_data: {},
        },
      });
      setIsCreateOpen(false);
      setEditor(EMPTY_EDITOR);
      setSuccessMessage("Product created.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to create product."));
    } finally {
      setIsSavingCreate(false);
    }
  }

  async function handleSaveEdit() {
    if (!selectedProduct) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsSavingEdit(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiRequest<Product>(`/api/v1/products/${selectedProduct.id}`, {
        method: "PATCH",
        authToken: token,
        body: {
          sku: editor.sku.trim() || undefined,
          name: editor.name.trim() || undefined,
          description: editor.description.trim() || null,
          product_type: editor.product_type,
          category: editor.category.trim() || null,
          unit_price: editor.unit_price.trim() ? parseFloat(editor.unit_price) : undefined,
          cost_price: editor.cost_price.trim() ? parseFloat(editor.cost_price) : null,
          is_active: editor.is_active,
          track_inventory: editor.track_inventory,
        },
      });
      setSelectedProduct(updated);
      setIsEditing(false);
      setSuccessMessage("Product updated.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to update product."));
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleDelete() {
    if (!selectedProduct) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<{ message: string }>(`/api/v1/products/${selectedProduct.id}`, { method: "DELETE", authToken: token });
      setSelectedProduct(null);
      setIsEditing(false);
      setSuccessMessage("Product deleted.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to delete product."));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Products</h1>
          <p className="mt-1 text-sm text-muted">Manage your product catalog.</p>
        </div>
        <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
          onClick={() => { setEditor(EMPTY_EDITOR); setIsCreateOpen(true); setError(null); }}>
          Add Product
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, SKU, or category"
          className="min-w-[240px] rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as typeof activeFilter)}
          className="rounded-md border border-border bg-background text-white px-3 py-2 text-sm">
          <option value="all">All products</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
        <button type="button" className="rounded-md border border-border px-3 py-2 text-sm text-on-surface-variant hover:bg-white/5"
          onClick={() => void load()}>Refresh</button>
        <button type="button" className="rounded-md border border-border px-3 py-2 text-sm text-on-surface-variant hover:bg-white/5"
          onClick={() => { setSearch(""); setActiveFilter("all"); setSortField("created"); setSortDirection("desc"); }}>Clear</button>
      </div>

      <p className="text-sm text-muted">Showing {visible.length} of {products.length} product{products.length === 1 ? "" : "s"}.</p>

      {successMessage && (
        <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">{successMessage}</div>
      )}
      {error && (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button type="button" className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium text-red-400 hover:bg-red-900/20" onClick={() => void load()}>Retry</button>
        </div>
      )}

      {isLoading ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">Loading products...</div>
      ) : visible.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">No products found for the current filters.</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-dim text-left">
              <tr>
                {(["sku", "name", "category", "price", "created"] as SortField[]).map((f) => (
                  <th key={f} className="px-4 py-3 font-medium text-on-surface-variant">
                    <button type="button" className="inline-flex items-center gap-1 hover:text-white capitalize"
                      onClick={() => handleSort(f)}>
                      {f === "price" ? "Unit Price" : f === "created" ? "Created" : f.charAt(0).toUpperCase() + f.slice(1)}
                      <SortIndicator active={sortField === f} direction={sortDirection} />
                    </button>
                  </th>
                ))}
                <th className="px-4 py-3 font-medium text-on-surface-variant">Type</th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Status</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((p) => (
                <tr key={p.id} className="cursor-pointer border-t border-border hover:bg-white/[0.02]"
                  onClick={() => { setSelectedProduct(p); setIsEditing(false); hydrateEditor(p); }}>
                  <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{p.sku}</td>
                  <td className="px-4 py-3 font-medium text-white">{p.name}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{p.category ?? "-"}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{fmt(p.unit_price)}</td>
                  <td className="px-4 py-3 text-on-surface-variant">{formatDate(p.created_at)}</td>
                  <td className="px-4 py-3 capitalize text-on-surface-variant">{p.product_type}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${statusBadge(p.is_active)}`}>
                      {p.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-on-surface-variant">
        <p>Page {page} of {totalPages}</p>
        <div className="flex gap-2">
          <button type="button" className="rounded-md border border-border px-3 py-1 disabled:opacity-50"
            disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <button type="button" className="rounded-md border border-border px-3 py-1 disabled:opacity-50"
            disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      </div>

      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => setIsCreateOpen(false)} aria-label="Close" />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Add Product</h2>
              <button type="button" className="rounded-md border border-border px-3 py-1 text-sm text-on-surface-variant hover:bg-white/5" onClick={() => setIsCreateOpen(false)}>Close</button>
            </div>
            <ProductForm editor={editor} onChange={setEditor} onSubmit={() => void handleCreate()} submitLabel={isSavingCreate ? "Creating..." : "Create Product"} disabled={isSavingCreate} />
          </aside>
        </div>
      )}

      {selectedProduct && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => { setSelectedProduct(null); setIsEditing(false); }} aria-label="Close" />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Product Details</h2>
              <button type="button" className="rounded-md border border-border px-3 py-1 text-sm text-on-surface-variant hover:bg-white/5" onClick={() => { setSelectedProduct(null); setIsEditing(false); }}>Close</button>
            </div>
            {!isEditing ? (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <DetailItem label="SKU" value={selectedProduct.sku} />
                  <DetailItem label="Name" value={selectedProduct.name} />
                  <DetailItem label="Type" value={selectedProduct.product_type} capitalize />
                  <DetailItem label="Category" value={selectedProduct.category ?? "-"} />
                  <DetailItem label="Unit Price" value={fmt(selectedProduct.unit_price)} />
                  <DetailItem label="Cost Price" value={selectedProduct.cost_price ? fmt(selectedProduct.cost_price) : "-"} />
                  <DetailItem label="Status" value={selectedProduct.is_active ? "Active" : "Inactive"} />
                  <DetailItem label="Track Inventory" value={selectedProduct.track_inventory ? "Yes" : "No"} />
                  <DetailItem label="Created" value={formatDate(selectedProduct.created_at)} />
                </div>
                {selectedProduct.description && (
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Description</p>
                    <p className="mt-1 rounded-md border border-border bg-white/5 p-3 text-sm text-on-surface-variant whitespace-pre-wrap">{selectedProduct.description}</p>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
                    onClick={() => { hydrateEditor(selectedProduct); setIsEditing(true); }}>Edit</button>
                  <button type="button" className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                    disabled={isDeleting} onClick={() => void handleDelete()}>
                    {isDeleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <ProductForm editor={editor} onChange={setEditor} onSubmit={() => void handleSaveEdit()} submitLabel={isSavingEdit ? "Saving..." : "Save"} disabled={isSavingEdit} />
                <button type="button" className="rounded-md border border-border px-4 py-2 text-sm text-on-surface-variant hover:bg-white/5"
                  onClick={() => { hydrateEditor(selectedProduct); setIsEditing(false); }}>Cancel</button>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

function SortIndicator({ active, direction }: { active: boolean; direction: SortDirection }) {
  if (!active) return <span className="text-on-surface-variant">↕</span>;
  return <span>{direction === "asc" ? "↑" : "↓"}</span>;
}

function DetailItem({ label, value, capitalize = false }: { label: string; value: string; capitalize?: boolean }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-sm text-on-surface-variant ${capitalize ? "capitalize" : ""}`}>{value}</p>
    </div>
  );
}

function ProductForm({ editor, onChange, onSubmit, submitLabel, disabled }: {
  editor: Editor;
  onChange: (e: Editor) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
}) {
  function set<K extends keyof Editor>(key: K, value: Editor[K]) { onChange({ ...editor, [key]: value }); }
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-sku">SKU *</label>
          <input id="p-sku" value={editor.sku} onChange={(e) => set("sku", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-name">Name *</label>
          <input id="p-name" value={editor.name} onChange={(e) => set("name", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-type">Type</label>
          <select id="p-type" value={editor.product_type} onChange={(e) => set("product_type", e.target.value as ProductType)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm">
            <option value="physical">Physical</option>
            <option value="digital">Digital</option>
            <option value="service">Service</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-category">Category</label>
          <input id="p-category" value={editor.category} onChange={(e) => set("category", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-price">Unit Price *</label>
          <input id="p-price" type="number" step="0.01" min="0" value={editor.unit_price} onChange={(e) => set("unit_price", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-cost">Cost Price</label>
          <input id="p-cost" type="number" step="0.01" min="0" value={editor.cost_price} onChange={(e) => set("cost_price", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="p-desc">Description</label>
        <textarea id="p-desc" rows={3} value={editor.description} onChange={(e) => set("description", e.target.value)} className="w-full rounded-md border border-border bg-background text-white px-3 py-2 text-sm" />
      </div>
      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-sm text-on-surface-variant cursor-pointer">
          <input type="checkbox" checked={editor.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Active
        </label>
        <label className="flex items-center gap-2 text-sm text-on-surface-variant cursor-pointer">
          <input type="checkbox" checked={editor.track_inventory} onChange={(e) => set("track_inventory", e.target.checked)} /> Track Inventory
        </label>
      </div>
      <button type="button" className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" onClick={onSubmit} disabled={disabled}>
        {submitLabel}
      </button>
    </div>
  );
}
