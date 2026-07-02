"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import type { InventoryLocation, Product, ProductListResponse, StockLevel } from "@/types/api";

interface LocationEditor {
  name: string;
  code: string;
  location_type: string;
  is_active: boolean;
}

const EMPTY_LOC_EDITOR: LocationEditor = { name: "", code: "", location_type: "warehouse", is_active: true };

interface AdjustForm {
  product_id: string;
  location_id: string;
  quantity_change: string;
  reason: string;
}

const EMPTY_ADJUST: AdjustForm = { product_id: "", location_id: "", quantity_change: "", reason: "" };

function toErrorMessage(err: unknown, fallback: string) {
  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}

function formatDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

export default function InventoryPage() {
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<InventoryLocation | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [locEditor, setLocEditor] = useState<LocationEditor>(EMPTY_LOC_EDITOR);

  const [adjustForm, setAdjustForm] = useState<AdjustForm>(EMPTY_ADJUST);
  const [isAdjusting, setIsAdjusting] = useState(false);
  const [adjustResult, setAdjustResult] = useState<StockLevel | null>(null);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsLoading(true);
    setError(null);
    try {
      const [locsRes, prodsRes] = await Promise.all([
        apiRequest<InventoryLocation[]>("/api/v1/inventory/locations?skip=0&limit=200", { method: "GET", authToken: token }),
        apiRequest<ProductListResponse>("/api/v1/products?skip=0&limit=500", { method: "GET", authToken: token }),
      ]);
      setLocations(locsRes);
      setProducts(prodsRes.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to load inventory data."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(t);
  }, [load]);

  function hydrateLocEditor(loc: InventoryLocation) {
    setLocEditor({ name: loc.name, code: loc.code ?? "", location_type: loc.location_type, is_active: loc.is_active });
  }

  async function handleCreateLocation() {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    if (!locEditor.name.trim()) { setError("Location name is required."); return; }
    setIsSavingCreate(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<InventoryLocation>("/api/v1/inventory/locations", {
        method: "POST",
        authToken: token,
        body: { name: locEditor.name.trim(), code: locEditor.code.trim() || null, location_type: locEditor.location_type, is_active: locEditor.is_active, meta_data: {} },
      });
      setIsCreateOpen(false);
      setLocEditor(EMPTY_LOC_EDITOR);
      setSuccessMessage("Location created.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to create location."));
    } finally {
      setIsSavingCreate(false);
    }
  }

  async function handleSaveLocEdit() {
    if (!selectedLocation) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsSavingEdit(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiRequest<InventoryLocation>(`/api/v1/inventory/locations/${selectedLocation.id}`, {
        method: "PATCH",
        authToken: token,
        body: { name: locEditor.name.trim() || undefined, code: locEditor.code.trim() || null, location_type: locEditor.location_type, is_active: locEditor.is_active },
      });
      setSelectedLocation(updated);
      setIsEditing(false);
      setSuccessMessage("Location updated.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to update location."));
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleDeleteLocation() {
    if (!selectedLocation) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<{ message: string }>(`/api/v1/inventory/locations/${selectedLocation.id}`, { method: "DELETE", authToken: token });
      setSelectedLocation(null);
      setIsEditing(false);
      setSuccessMessage("Location deleted.");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to delete location."));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleAdjustStock() {
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }
    if (!adjustForm.product_id || !adjustForm.location_id || !adjustForm.quantity_change) {
      setError("Product, location, and quantity change are all required.");
      return;
    }
    setIsAdjusting(true);
    setError(null);
    setSuccessMessage(null);
    setAdjustResult(null);
    try {
      const result = await apiRequest<StockLevel>("/api/v1/inventory/stock/adjust", {
        method: "POST",
        authToken: token,
        body: {
          product_id: adjustForm.product_id,
          location_id: adjustForm.location_id,
          quantity_change: parseInt(adjustForm.quantity_change, 10),
          reason: adjustForm.reason.trim() || null,
        },
      });
      setAdjustResult(result);
      setSuccessMessage(`Stock adjusted. New quantity: ${result.quantity}, Available: ${result.available}`);
      setAdjustForm(EMPTY_ADJUST);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { logout(); window.location.replace("/login"); return; }
      setError(toErrorMessage(e, "Unable to adjust stock."));
    } finally {
      setIsAdjusting(false);
    }
  }

  return (
    <section className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Inventory</h1>
          <p className="mt-1 text-sm text-muted">Manage warehouse locations and adjust stock levels.</p>
        </div>
        <button type="button" className="erp-button-primary px-4 py-2 text-sm font-semibold"
          onClick={() => { setLocEditor(EMPTY_LOC_EDITOR); setIsCreateOpen(true); setError(null); }}>
          Add Location
        </button>
      </div>

      {successMessage && <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">{successMessage}</div>}
      {error && (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button type="button" className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium text-red-400 hover:bg-red-900/20" onClick={() => void load()}>Retry</button>
        </div>
      )}

      {/* Locations */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-[#ccc]">Locations</h2>
        {isLoading ? (
          <div className="erp-panel p-5 text-sm text-muted">Loading locations...</div>
        ) : locations.length === 0 ? (
          <div className="erp-panel p-5 text-sm text-muted">No locations yet. Add one to get started.</div>
        ) : (
          <div className="overflow-x-auto erp-panel">
            <table className="min-w-full text-sm">
              <thead className="bg-[#111e35] text-left">
                <tr>
                  <th className="px-4 py-3 font-medium text-[#aaa]">Name</th>
                  <th className="px-4 py-3 font-medium text-[#aaa]">Code</th>
                  <th className="px-4 py-3 font-medium text-[#aaa]">Type</th>
                  <th className="px-4 py-3 font-medium text-[#aaa]">Status</th>
                  <th className="px-4 py-3 font-medium text-[#aaa]">Created</th>
                </tr>
              </thead>
              <tbody>
                {locations.map((loc) => (
                  <tr key={loc.id} className="cursor-pointer border-t border-outline-variant/70 hover:bg-surface-container-high/70"
                    onClick={() => { setSelectedLocation(loc); setIsEditing(false); hydrateLocEditor(loc); }}>
                    <td className="px-4 py-3 font-medium text-white">{loc.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-[#aaa]">{loc.code ?? "-"}</td>
                    <td className="px-4 py-3 capitalize text-[#aaa]">{loc.location_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${loc.is_active ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-[#aaa]"}`}>
                        {loc.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[#aaa]">{formatDate(loc.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Stock Adjustment */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-[#ccc]">Stock Adjustment</h2>
        <div className="erp-panel p-5">
          <p className="mb-4 text-sm text-muted">Add or subtract stock for a product at a specific location.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="adj-product">Product</label>
              <select id="adj-product" value={adjustForm.product_id} onChange={(e) => setAdjustForm((f) => ({ ...f, product_id: e.target.value }))}
                className="erp-input w-full px-3 py-2 text-sm">
                <option value="">— Select product —</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="adj-location">Location</label>
              <select id="adj-location" value={adjustForm.location_id} onChange={(e) => setAdjustForm((f) => ({ ...f, location_id: e.target.value }))}
                className="erp-input w-full px-3 py-2 text-sm">
                <option value="">— Select location —</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="adj-qty">Quantity Change</label>
              <input id="adj-qty" type="number" value={adjustForm.quantity_change} placeholder="+50 or -10"
                onChange={(e) => setAdjustForm((f) => ({ ...f, quantity_change: e.target.value }))}
                className="erp-input w-full px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="adj-reason">Reason</label>
              <input id="adj-reason" type="text" value={adjustForm.reason} placeholder="e.g. received shipment"
                onChange={(e) => setAdjustForm((f) => ({ ...f, reason: e.target.value }))}
                className="erp-input w-full px-3 py-2 text-sm" />
            </div>
          </div>
          <button type="button" className="mt-4 erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60"
            onClick={() => void handleAdjustStock()} disabled={isAdjusting}>
            {isAdjusting ? "Adjusting..." : "Adjust Stock"}
          </button>
          {adjustResult && (
            <div className="mt-4 rounded-md border border-border bg-white/5 p-4 text-sm text-[#ccc]">
              <p className="font-medium">Adjustment applied</p>
              <p>Quantity: <strong>{adjustResult.quantity}</strong> &bull; Reserved: {adjustResult.reserved} &bull; Available: <strong>{adjustResult.available}</strong></p>
              <p className="text-xs text-muted mt-1">Reorder point: {adjustResult.reorder_point}</p>
            </div>
          )}
        </div>
      </div>

      {/* Location create panel */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => setIsCreateOpen(false)} aria-label="Close" />
          <aside className="h-full w-full max-w-md overflow-y-auto border-l border-outline-variant bg-[#0f1c33] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Add Location</h2>
              <button type="button" className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high" onClick={() => setIsCreateOpen(false)}>Close</button>
            </div>
            <LocationForm editor={locEditor} onChange={setLocEditor} onSubmit={() => void handleCreateLocation()} submitLabel={isSavingCreate ? "Creating..." : "Create Location"} disabled={isSavingCreate} />
          </aside>
        </div>
      )}

      {/* Location detail panel */}
      {selectedLocation && (
        <div className="fixed inset-0 z-40 flex">
          <button type="button" className="h-full flex-1 bg-slate-900/30" onClick={() => { setSelectedLocation(null); setIsEditing(false); }} aria-label="Close" />
          <aside className="h-full w-full max-w-md overflow-y-auto border-l border-outline-variant bg-[#0f1c33] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Location Details</h2>
              <button type="button" className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high" onClick={() => { setSelectedLocation(null); setIsEditing(false); }}>Close</button>
            </div>
            {!isEditing ? (
              <div className="space-y-4">
                <div className="grid gap-3 text-sm sm:grid-cols-2">
                  <DetailItem label="Name" value={selectedLocation.name} />
                  <DetailItem label="Code" value={selectedLocation.code ?? "-"} />
                  <DetailItem label="Type" value={selectedLocation.location_type} capitalize />
                  <DetailItem label="Status" value={selectedLocation.is_active ? "Active" : "Inactive"} />
                  <DetailItem label="Created" value={formatDate(selectedLocation.created_at)} />
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="erp-button-primary px-4 py-2 text-sm font-semibold"
                    onClick={() => { hydrateLocEditor(selectedLocation); setIsEditing(true); }}>Edit</button>
                  <button type="button" className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                    disabled={isDeleting} onClick={() => void handleDeleteLocation()}>
                    {isDeleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <LocationForm editor={locEditor} onChange={setLocEditor} onSubmit={() => void handleSaveLocEdit()} submitLabel={isSavingEdit ? "Saving..." : "Save"} disabled={isSavingEdit} />
                <button type="button" className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
                  onClick={() => { hydrateLocEditor(selectedLocation); setIsEditing(false); }}>Cancel</button>
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

function DetailItem({ label, value, capitalize = false }: { label: string; value: string; capitalize?: boolean }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-sm text-[#ccc] ${capitalize ? "capitalize" : ""}`}>{value}</p>
    </div>
  );
}

function LocationForm({ editor, onChange, onSubmit, submitLabel, disabled }: {
  editor: LocationEditor;
  onChange: (e: LocationEditor) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
}) {
  function set<K extends keyof LocationEditor>(key: K, value: LocationEditor[K]) { onChange({ ...editor, [key]: value }); }
  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="l-name">Name *</label>
        <input id="l-name" value={editor.name} onChange={(e) => set("name", e.target.value)} className="erp-input w-full px-3 py-2 text-sm" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="l-code">Code</label>
          <input id="l-code" value={editor.code} onChange={(e) => set("code", e.target.value)} className="erp-input w-full px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="l-type">Type</label>
          <select id="l-type" value={editor.location_type} onChange={(e) => set("location_type", e.target.value)} className="erp-input w-full px-3 py-2 text-sm">
            <option value="warehouse">Warehouse</option>
            <option value="store">Store</option>
            <option value="virtual">Virtual</option>
          </select>
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-[#aaa] cursor-pointer">
        <input type="checkbox" checked={editor.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Active
      </label>
      <button type="button" className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60" onClick={onSubmit} disabled={disabled}>
        {submitLabel}
      </button>
    </div>
  );
}


