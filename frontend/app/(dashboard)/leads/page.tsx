"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import { SalesCrmSubNav } from "@/components/SalesCrmSubNav";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type { Customer, CustomerListResponse, Lead, LeadGenSearchResponse, LeadListResponse } from "@/types/api";

type LeadStatusUi = "all" | "new" | "contacted" | "qualified" | "converted" | "lost";
type LeadSortField = "name" | "email" | "status" | "source" | "created";
type SortDirection = "asc" | "desc";

interface LeadEditorState {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  company: string;
  status: Exclude<LeadStatusUi, "all">;
  source: string;
  notes: string;
}

const PAGE_SIZE = 20;

function toUiStatus(status: Lead["status"]): Exclude<LeadStatusUi, "all"> {
  if (status === "won") {
    return "converted";
  }
  return status;
}

function toBackendStatus(status: Exclude<LeadStatusUi, "all">): Lead["status"] {
  if (status === "converted") {
    return "won";
  }
  return status;
}

function statusBadgeClass(status: Exclude<LeadStatusUi, "all">): string {
  if (status === "new") return "bg-white/10 text-slate-400";
  if (status === "contacted") return "bg-blue-500/20 text-blue-300";
  if (status === "qualified") return "bg-amber-500/20 text-amber-300";
  if (status === "converted") return "bg-emerald-500/20 text-emerald-300";
  return "bg-rose-500/20 text-rose-300";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function splitName(name: string | null | undefined): { firstName: string; lastName: string } {
  const safe = (name ?? "").trim();
  if (!safe) {
    return { firstName: "", lastName: "" };
  }
  const [firstName, ...rest] = safe.split(/\s+/);
  return { firstName, lastName: rest.join(" ") };
}

function fullName(firstName: string, lastName: string): string {
  return `${firstName} ${lastName}`.trim();
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function csvValue(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

function downloadCsv(filename: string, rows: string[][]): void {
  const csvBody = rows.map((row) => row.map(csvValue).join(",")).join("\n");
  const blob = new Blob([csvBody], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [customersById, setCustomersById] = useState<Record<string, Customer>>({});
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<LeadStatusUi>("all");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sortField, setSortField] = useState<LeadSortField>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [bulkStatus, setBulkStatus] = useState<Exclude<LeadStatusUi, "all">>("contacted");
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const [isFindLeadsOpen, setIsFindLeadsOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [isSearchingLeads, setIsSearchingLeads] = useState(false);
  const [findResultMessage, setFindResultMessage] = useState<string | null>(null);
  const [findError, setFindError] = useState<string | null>(null);

  const [isCreatingOrder, setIsCreatingOrder] = useState(false);
  const [orderNotes, setOrderNotes] = useState("");
  const [isOrderSaving, setIsOrderSaving] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState<{ id: string; number: string } | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editor, setEditor] = useState<LeadEditorState>({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    company: "",
    status: "new",
    source: "",
    notes: "",
  });

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const visibleLeads = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = leads.filter((lead) => {
      const customer = lead.customer_id ? customersById[lead.customer_id] : undefined;
      const name = customer?.name?.toLowerCase() ?? "";
      const email = customer?.email?.toLowerCase() ?? "";
      return !query || name.includes(query) || email.includes(query);
    });

    filtered.sort((left, right) => {
      const leftCustomer = left.customer_id ? customersById[left.customer_id] : undefined;
      const rightCustomer = right.customer_id ? customersById[right.customer_id] : undefined;
      if (sortField === "name") {
        const leftName = (leftCustomer?.name ?? "").toLowerCase();
        const rightName = (rightCustomer?.name ?? "").toLowerCase();
        return leftName.localeCompare(rightName);
      }
      if (sortField === "email") {
        const leftEmail = (leftCustomer?.email ?? "").toLowerCase();
        const rightEmail = (rightCustomer?.email ?? "").toLowerCase();
        return leftEmail.localeCompare(rightEmail);
      }
      if (sortField === "status") {
        return toUiStatus(left.status).localeCompare(toUiStatus(right.status));
      }
      if (sortField === "source") {
        return (left.source ?? "").localeCompare(right.source ?? "");
      }
      return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
    });

    if (sortDirection === "desc") {
      filtered.reverse();
    }

    return filtered;
  }, [customersById, leads, search, sortDirection, sortField]);

  const visibleLeadIdSet = useMemo(
    () => new Set(visibleLeads.map((lead) => lead.id)),
    [visibleLeads],
  );

  const selectedVisibleLeadIds = useMemo(
    () => selectedLeadIds.filter((leadId) => visibleLeadIdSet.has(leadId)),
    [selectedLeadIds, visibleLeadIdSet],
  );

  const allVisibleSelected =
    visibleLeads.length > 0 && selectedVisibleLeadIds.length === visibleLeads.length;

  const hydrateEditorFromLead = useCallback(
    (lead: Lead) => {
      const customer = lead.customer_id ? customersById[lead.customer_id] : undefined;
      const nameParts = splitName(customer?.name);
      setEditor({
        firstName: nameParts.firstName,
        lastName: nameParts.lastName,
        email: customer?.email ?? "",
        phone: customer?.phone ?? "",
        company: customer?.company ?? "",
        status: toUiStatus(lead.status),
        source: lead.source ?? "",
        notes: lead.notes ?? "",
      });
    },
    [customersById],
  );

  const loadLeads = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsLoading(true);
    setError(null);

    const skip = (page - 1) * PAGE_SIZE;
    const statusQuery =
      statusFilter === "all"
        ? ""
        : `&status=${encodeURIComponent(toBackendStatus(statusFilter))}`;

    try {
      const [leadResponse, customerResponse] = await Promise.all([
        apiRequest<LeadListResponse>(
          `/api/v1/leads?skip=${skip}&limit=${PAGE_SIZE}${statusQuery}`,
          {
            method: "GET",
            authToken: token,
          },
        ),
        apiRequest<CustomerListResponse>("/api/v1/customers?skip=0&limit=1000", {
          method: "GET",
          authToken: token,
        }),
      ]);

      const customerMap: Record<string, Customer> = {};
      for (const customer of customerResponse.items) {
        customerMap[customer.id] = customer;
      }

      setLeads(leadResponse.items);
      setTotal(leadResponse.total);
      setCustomersById(customerMap);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to load leads.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadLeads();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadLeads]);

  const searchParams = useSearchParams();
  useEffect(() => {
    const openId = searchParams.get("open");
    if (openId) {
      void openLeadDetails({ id: openId } as Lead);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSortChange = useCallback((field: LeadSortField) => {
    setSortField((previousField) => {
      if (previousField === field) {
        setSortDirection((previousDirection) =>
          previousDirection === "asc" ? "desc" : "asc",
        );
        return previousField;
      }
      setSortDirection(field === "created" ? "desc" : "asc");
      return field;
    });
  }, []);

  const handleToggleAllVisible = useCallback(() => {
    if (visibleLeads.length === 0) {
      return;
    }

    setSelectedLeadIds((previous) => {
      if (allVisibleSelected) {
        const visible = new Set(visibleLeads.map((lead) => lead.id));
        return previous.filter((leadId) => !visible.has(leadId));
      }

      const merged = new Set(previous);
      for (const lead of visibleLeads) {
        merged.add(lead.id);
      }
      return Array.from(merged);
    });
  }, [allVisibleSelected, visibleLeads]);

  const handleToggleOne = useCallback((leadId: string) => {
    setSelectedLeadIds((previous) => {
      if (previous.includes(leadId)) {
        return previous.filter((id) => id !== leadId);
      }
      return [...previous, leadId];
    });
  }, []);

  const handleBulkStatusUpdate = useCallback(async () => {
    if (selectedVisibleLeadIds.length === 0) {
      return;
    }

    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsBulkUpdating(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const outcomes = await Promise.allSettled(
        selectedVisibleLeadIds.map((leadId) =>
          apiRequest<Lead>(`/api/v1/leads/${leadId}`, {
            method: "PATCH",
            authToken: token,
            body: {
              status: toBackendStatus(bulkStatus),
            },
          }),
        ),
      );

      const successCount = outcomes.filter((outcome) => outcome.status === "fulfilled").length;
      const failureCount = outcomes.length - successCount;

      if (successCount > 0) {
        setSuccessMessage(
          `Updated ${successCount} lead${successCount === 1 ? "" : "s"} to ${bulkStatus}.`,
        );
        setSelectedLeadIds((previous) =>
          previous.filter((leadId) => !selectedVisibleLeadIds.includes(leadId)),
        );
        await loadLeads();
      }

      if (failureCount > 0) {
        const firstFailure = outcomes.find(
          (outcome): outcome is PromiseRejectedResult => outcome.status === "rejected",
        );
        setError(
          `${toErrorMessage(firstFailure?.reason, "Unable to update selected leads.")} (${failureCount} failed${successCount > 0 ? `, ${successCount} succeeded` : ""})`,
        );
      }
    } finally {
      setIsBulkUpdating(false);
    }
  }, [bulkStatus, loadLeads, selectedVisibleLeadIds]);

  const exportVisibleLeadsCsv = useCallback(() => {
    if (visibleLeads.length === 0) {
      return;
    }

    const rows: string[][] = [
      ["Lead ID", "Name", "Email", "Phone", "Status", "Source", "Created", "Updated"],
    ];

    for (const lead of visibleLeads) {
      const customer = lead.customer_id ? customersById[lead.customer_id] : undefined;
      const nameParts = splitName(customer?.name);
      rows.push([
        lead.id,
        fullName(nameParts.firstName, nameParts.lastName) || "Unknown",
        customer?.email ?? "",
        customer?.phone ?? "",
        toUiStatus(lead.status),
        lead.source ?? "",
        formatDate(lead.created_at),
        formatDate(lead.updated_at),
      ]);
    }

    const datePart = new Date().toISOString().slice(0, 10);
    downloadCsv(`leads-${datePart}.csv`, rows);
  }, [customersById, visibleLeads]);

  async function handleCreateSalesOrder() {
    if (!selectedLead) return;
    const token = getStoredToken();
    if (!token) { logout(); window.location.replace("/login"); return; }

    setIsOrderSaving(true);
    setOrderError(null);
    try {
      const body: Record<string, unknown> = {};
      if (selectedLead.customer_id) body.customer_id = selectedLead.customer_id;
      body.lead_id = selectedLead.id;
      if (orderNotes.trim()) body.notes = orderNotes.trim();

      const created = await apiRequest<{ id: string; order_number: string }>(
        "/api/v1/sales-orders",
        { method: "POST", body, authToken: token },
      );
      setOrderSuccess({ id: created.id, number: created.order_number });
      setIsCreatingOrder(false);
      setOrderNotes("");
    } catch (err: unknown) {
      setOrderError(err instanceof Error ? err.message : "Failed to create sales order.");
    } finally {
      setIsOrderSaving(false);
    }
  }

  async function openLeadDetails(lead: Lead) {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setSelectedLead(lead);
    setIsDetailsLoading(true);
    setIsEditing(false);
    setError(null);

    try {
      const fullLead = await apiRequest<Lead>(`/api/v1/leads/${lead.id}`, {
        method: "GET",
        authToken: token,
      });
      setSelectedLead(fullLead);
      hydrateEditorFromLead(fullLead);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load lead details.",
      );
    } finally {
      setIsDetailsLoading(false);
    }
  }

  function resetCreateForm() {
    setEditor({
      firstName: "",
      lastName: "",
      email: "",
      phone: "",
      company: "",
      status: "new",
      source: "",
      notes: "",
    });
  }

  async function handleFindLeads() {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    if (!findQuery.trim()) {
      setFindError("Enter what you're looking for, e.g. \"plumbers in Johannesburg\".");
      return;
    }

    setIsSearchingLeads(true);
    setFindError(null);
    setFindResultMessage(null);

    try {
      const result = await apiRequest<LeadGenSearchResponse>("/api/v1/leads/find", {
        method: "POST",
        authToken: token,
        body: { query: findQuery.trim(), max_results: 10 },
      });

      setFindResultMessage(
        result.created_count > 0
          ? `Found ${result.created_count} new lead${result.created_count === 1 ? "" : "s"}` +
            (result.skipped_duplicates > 0 ? ` (${result.skipped_duplicates} already in your pipeline).` : ".")
          : `No new leads - ${result.skipped_duplicates} result(s) were already in your pipeline.`
      );
      await loadLeads();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setFindError(requestError instanceof Error ? requestError.message : "Search failed.");
    } finally {
      setIsSearchingLeads(false);
    }
  }

  async function handleCreateLead() {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    const name = fullName(editor.firstName, editor.lastName);
    if (!name) {
      setError("First and/or last name is required.");
      return;
    }

    setIsSavingCreate(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const customer = await apiRequest<Customer>("/api/v1/customers", {
        method: "POST",
        authToken: token,
        body: {
          name,
          email: editor.email.trim() || null,
          phone: editor.phone.trim() || null,
          company: editor.company.trim() || null,
          notes: editor.notes.trim() || null,
        },
      });

      await apiRequest<Lead>("/api/v1/leads", {
        method: "POST",
        authToken: token,
        body: {
          customer_id: customer.id,
          status: toBackendStatus(editor.status),
          source: editor.source.trim() || null,
          notes: editor.notes.trim() || null,
        },
      });

      setIsCreateOpen(false);
      resetCreateForm();
      await loadLeads();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to create lead.",
      );
    } finally {
      setIsSavingCreate(false);
    }
  }

  async function handleSaveLeadEdits() {
    if (!selectedLead) return;
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    const name = fullName(editor.firstName, editor.lastName);
    if (!name) {
      setError("First and/or last name is required.");
      return;
    }

    setIsSavingEdit(true);
    setError(null);
    setSuccessMessage(null);

    try {
      let customerId = selectedLead.customer_id;
      if (customerId) {
        await apiRequest<Customer>(`/api/v1/customers/${customerId}`, {
          method: "PATCH",
          authToken: token,
          body: {
            name,
            email: editor.email.trim() || null,
            phone: editor.phone.trim() || null,
            company: editor.company.trim() || null,
            notes: editor.notes.trim() || null,
          },
        });
      } else {
        const createdCustomer = await apiRequest<Customer>("/api/v1/customers", {
          method: "POST",
          authToken: token,
          body: {
            name,
            email: editor.email.trim() || null,
            phone: editor.phone.trim() || null,
            company: editor.company.trim() || null,
            notes: editor.notes.trim() || null,
          },
        });
        customerId = createdCustomer.id;
      }

      const updatedLead = await apiRequest<Lead>(`/api/v1/leads/${selectedLead.id}`, {
        method: "PATCH",
        authToken: token,
        body: {
          customer_id: customerId,
          status: toBackendStatus(editor.status),
          source: editor.source.trim() || null,
          notes: editor.notes.trim() || null,
        },
      });

      setSelectedLead(updatedLead);
      setIsEditing(false);
      await loadLeads();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to update lead.",
      );
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleDeleteLead() {
    if (!selectedLead) return;
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<{ message: string }>(`/api/v1/leads/${selectedLead.id}`, {
        method: "DELETE",
        authToken: token,
      });
      setSelectedLead(null);
      setIsEditing(false);
      await loadLeads();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to delete lead.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  const selectedCustomer =
    selectedLead?.customer_id ? customersById[selectedLead.customer_id] : undefined;
  const selectedNameParts = splitName(selectedCustomer?.name);

  return (
    <section className="space-y-5">
      <SalesCrmSubNav />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Leads</h1>
          <p className="mt-1 text-sm text-muted">
            Manage lead pipeline, customer identity, and conversion status.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="erp-panel px-4 py-2 text-sm font-semibold text-tertiary-fixed-dim transition-colors hover:border-tertiary-fixed-dim/40"
            onClick={() => {
              setFindQuery("");
              setFindError(null);
              setFindResultMessage(null);
              setIsFindLeadsOpen(true);
            }}
          >
            Find Leads
          </button>
          <button
            type="button"
            className="erp-button-primary px-4 py-2 text-sm font-semibold"
            onClick={() => {
              resetCreateForm();
              setIsCreateOpen(true);
              setError(null);
            }}
          >
            Add Lead
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name or email"
          className="min-w-[250px] erp-input w-full px-3 py-2 text-sm"
        />
        <select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value as LeadStatusUi);
            setPage(1);
          }}
          className="erp-input w-full px-3 py-2 text-sm"
        >
          <option value="all">All statuses</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="converted">Converted</option>
          <option value="lost">Lost</option>
        </select>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high"
          onClick={() => void loadLeads()}
        >
          Refresh
        </button>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high disabled:opacity-50"
          onClick={exportVisibleLeadsCsv}
          disabled={visibleLeads.length === 0}
        >
          Export CSV
        </button>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high"
          onClick={() => {
            setSearch("");
            setStatusFilter("all");
            setSortField("created");
            setSortDirection("desc");
          }}
        >
          Clear
        </button>
      </div>

      <p className="text-sm text-muted">
        Showing {visibleLeads.length} of {leads.length} lead{leads.length === 1 ? "" : "s"}.
      </p>

      {selectedVisibleLeadIds.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-white/5 px-4 py-3 text-sm">
          <p className="text-on-surface-variant">
            Selected {selectedVisibleLeadIds.length} lead
            {selectedVisibleLeadIds.length === 1 ? "" : "s"}.
          </p>
          <div className="flex items-center gap-2">
            <select
              value={bulkStatus}
              onChange={(event) =>
                setBulkStatus(event.target.value as Exclude<LeadStatusUi, "all">)
              }
              className="rounded-md border border-border bg-background text-white px-3 py-1.5 text-sm capitalize"
            >
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="qualified">Qualified</option>
              <option value="converted">Converted</option>
              <option value="lost">Lost</option>
            </select>
            <button
              type="button"
              className="rounded-md border border-blue-700/40 px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-blue-900/20 disabled:opacity-60"
              onClick={() => void handleBulkStatusUpdate()}
              disabled={isBulkUpdating}
            >
              {isBulkUpdating ? "Updating..." : "Apply Status"}
            </button>
          </div>
        </div>
      ) : null}

      {successMessage ? (
        <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">
          {successMessage}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button
            type="button"
            className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium text-red-400 hover:bg-red-900/20"
            onClick={() => void loadLeads()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="erp-panel p-5 text-sm text-muted">
          Loading leads...
        </div>
      ) : visibleLeads.length === 0 ? (
        <div className="erp-panel p-5 text-sm text-muted">
          No leads found for the current filters.
        </div>
      ) : (
        <div className="overflow-x-auto erp-panel">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-dim text-left">
              <tr>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={handleToggleAllVisible}
                    aria-label="Select all visible leads"
                  />
                </th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("name")}
                  >
                    Name
                    <SortIndicator active={sortField === "name"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("email")}
                  >
                    Email
                    <SortIndicator active={sortField === "email"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">Phone</th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("status")}
                  >
                    Status
                    <SortIndicator active={sortField === "status"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("source")}
                  >
                    Source
                    <SortIndicator active={sortField === "source"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-on-surface-variant">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("created")}
                  >
                    Created
                    <SortIndicator active={sortField === "created"} direction={sortDirection} />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleLeads.map((lead) => {
                const customer = lead.customer_id ? customersById[lead.customer_id] : undefined;
                const nameParts = splitName(customer?.name);
                const displayStatus = toUiStatus(lead.status);
                return (
                  <tr
                    key={lead.id}
                    className="cursor-pointer border-t border-outline-variant/70 hover:bg-surface-container-high/70"
                    onClick={() => void openLeadDetails(lead)}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.includes(lead.id)}
                        onClick={(event) => event.stopPropagation()}
                        onChange={() => handleToggleOne(lead.id)}
                        aria-label={`Select ${customer?.name ?? lead.id}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-white">
                      {fullName(nameParts.firstName, nameParts.lastName) || "Unknown"}
                    </td>
                    <td className="px-4 py-3 text-on-surface-variant">{customer?.email ?? "-"}</td>
                    <td className="px-4 py-3 text-on-surface-variant">{customer?.phone ?? "-"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-1 text-xs font-semibold capitalize",
                          statusBadgeClass(displayStatus),
                        ].join(" ")}
                      >
                        {displayStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-on-surface-variant">{lead.source ?? "-"}</td>
                    <td className="px-4 py-3 text-on-surface-variant">{formatDate(lead.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-on-surface-variant">
        <p>
          Page {page} of {totalPages}
        </p>
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

      {isCreateOpen ? (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => setIsCreateOpen(false)}
            aria-label="Close create lead panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Add Lead</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => setIsCreateOpen(false)}
              >
                Close
              </button>
            </div>
            <LeadForm
              editor={editor}
              onChange={setEditor}
              onSubmit={() => void handleCreateLead()}
              submitLabel={isSavingCreate ? "Creating..." : "Create Lead"}
              disabled={isSavingCreate}
            />
          </aside>
        </div>
      ) : null}

      {isFindLeadsOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center">
          <button
            type="button"
            className="absolute inset-0 h-full w-full bg-slate-900/30"
            onClick={() => setIsFindLeadsOpen(false)}
            aria-label="Close find leads panel"
          />
          <div className="erp-panel relative z-10 w-full max-w-lg p-6">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Find Leads</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => setIsFindLeadsOpen(false)}
              >
                Close
              </button>
            </div>
            <p className="mb-4 text-xs text-on-surface-variant">
              Searches Google for real businesses matching what you type, and creates a lead for
              each new result automatically.
            </p>

            <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="find-leads-query">
              What are you looking for?
            </label>
            <input
              id="find-leads-query"
              type="text"
              className="erp-input w-full px-3 py-2 text-sm"
              placeholder="e.g. plumbers in Johannesburg"
              value={findQuery}
              onChange={(event) => setFindQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleFindLeads();
              }}
              disabled={isSearchingLeads}
            />

            {findError && (
              <p className="mt-3 rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
                {findError}
              </p>
            )}
            {findResultMessage && (
              <p className="mt-3 rounded-md border border-tertiary-fixed-dim/30 bg-tertiary-fixed-dim/10 px-3 py-2 text-sm text-tertiary-fixed-dim">
                {findResultMessage}
              </p>
            )}

            <button
              type="button"
              className="erp-button-primary mt-4 w-full py-2 text-sm font-semibold disabled:opacity-60"
              onClick={() => void handleFindLeads()}
              disabled={isSearchingLeads}
            >
              {isSearchingLeads ? "Searching..." : "Search"}
            </button>
          </div>
        </div>
      ) : null}

      {selectedLead ? (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => {
              setSelectedLead(null);
              setIsEditing(false);
              setIsCreatingOrder(false);
              setOrderSuccess(null);
              setOrderError(null);
              setOrderNotes("");
            }}
            aria-label="Close lead details panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-surface p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Lead Details</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => {
                  setSelectedLead(null);
                  setIsEditing(false);
                  setIsCreatingOrder(false);
                  setOrderSuccess(null);
                  setOrderError(null);
                  setOrderNotes("");
                }}
              >
                Close
              </button>
            </div>

            {isDetailsLoading ? (
              <p className="text-sm text-muted">Loading lead details...</p>
            ) : (
              <div className="space-y-4">
                {!isEditing ? (
                  <>
                    <div className="grid gap-3 text-sm sm:grid-cols-2">
                      <DetailItem label="First Name" value={selectedNameParts.firstName || "-"} />
                      <DetailItem label="Last Name" value={selectedNameParts.lastName || "-"} />
                      <DetailItem label="Email" value={selectedCustomer?.email ?? "-"} />
                      <DetailItem label="Phone" value={selectedCustomer?.phone ?? "-"} />
                      <DetailItem label="Company" value={selectedCustomer?.company ?? "-"} />
                      <DetailItem
                        label="Status"
                        value={toUiStatus(selectedLead.status)}
                        capitalize
                      />
                      <DetailItem label="Source" value={selectedLead.source ?? "-"} />
                      <DetailItem label="Created" value={formatDate(selectedLead.created_at)} />
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted">Notes</p>
                      <p className="mt-1 rounded-md border border-border bg-white/5 p-3 text-sm text-on-surface-variant whitespace-pre-wrap">
                        {selectedLead.notes?.trim() || "No notes"}
                      </p>
                    </div>
                    <ActivityTimeline entityType="lead" entityId={selectedLead.id} />
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="erp-button-primary px-4 py-2 text-sm font-semibold"
                        onClick={() => {
                          if (selectedLead) {
                            hydrateEditorFromLead(selectedLead);
                          }
                          setIsEditing(true);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                        disabled={isDeleting}
                        onClick={() => void handleDeleteLead()}
                      >
                        {isDeleting ? "Deleting..." : "Delete"}
                      </button>
                      {selectedLead.status === "won" && !orderSuccess && (
                        <button
                          type="button"
                          className="rounded-md border border-emerald-700/40 px-4 py-2 text-sm font-semibold text-emerald-400 hover:bg-emerald-900/20"
                          onClick={() => { setIsCreatingOrder(true); setOrderError(null); }}
                        >
                          Create Sales Order
                        </button>
                      )}
                    </div>

                    {orderSuccess && (
                      <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">
                        Sales order <strong>{orderSuccess.number}</strong> created.{" "}
                        <a
                          href="/sales-orders"
                          className="underline hover:text-emerald-300"
                        >
                          View in Sales Orders →
                        </a>
                      </div>
                    )}

                    {isCreatingOrder && (
                      <div className="rounded-md border border-outline-variant bg-white/5 p-4 space-y-3">
                        <p className="text-sm font-medium text-white">New Sales Order</p>
                        <p className="text-xs text-slate-400">
                          Creates a draft order linked to{" "}
                          <strong className="text-white">
                            {selectedCustomer?.name ?? "this lead"}
                          </strong>
                          . Line items can be added from the Sales Orders page.
                        </p>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-400">
                            Notes (optional)
                          </label>
                          <textarea
                            rows={2}
                            value={orderNotes}
                            onChange={(e) => setOrderNotes(e.target.value)}
                            placeholder="e.g. Follow up from discovery call"
                            className="erp-input w-full px-3 py-2 text-sm"
                          />
                        </div>
                        {orderError && (
                          <p className="text-xs text-rose-400">{orderError}</p>
                        )}
                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={isOrderSaving}
                            className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60"
                            onClick={() => void handleCreateSalesOrder()}
                          >
                            {isOrderSaving ? "Creating…" : "Confirm"}
                          </button>
                          <button
                            type="button"
                            className="rounded-md border border-border px-4 py-2 text-sm text-slate-400 hover:bg-white/5"
                            onClick={() => { setIsCreatingOrder(false); setOrderError(null); }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <LeadForm
                      editor={editor}
                      onChange={setEditor}
                      onSubmit={() => void handleSaveLeadEdits()}
                      submitLabel={isSavingEdit ? "Saving..." : "Save"}
                      disabled={isSavingEdit}
                    />
                    <button
                      type="button"
                      className="rounded-md border border-border px-4 py-2 text-sm text-on-surface-variant hover:bg-white/5"
                      onClick={() => {
                        if (selectedLead) hydrateEditorFromLead(selectedLead);
                        setIsEditing(false);
                      }}
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            )}
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function SortIndicator({
  active,
  direction,
}: {
  active: boolean;
  direction: SortDirection;
}) {
  if (!active) {
    return <span className="text-on-surface-variant">↕</span>;
  }
  return <span>{direction === "asc" ? "↑" : "↓"}</span>;
}

function DetailItem({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-sm text-on-surface-variant ${capitalize ? "capitalize" : ""}`}>{value}</p>
    </div>
  );
}

function LeadForm({
  editor,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
}: {
  editor: LeadEditorState;
  onChange: (next: LeadEditorState) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
}) {
  function update<K extends keyof LeadEditorState>(key: K, value: LeadEditorState[K]) {
    onChange({ ...editor, [key]: value });
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="first-name">
            First Name
          </label>
          <input
            id="first-name"
            value={editor.firstName}
            onChange={(event) => update("firstName", event.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="last-name">
            Last Name
          </label>
          <input
            id="last-name"
            value={editor.lastName}
            onChange={(event) => update("lastName", event.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={editor.email}
            onChange={(event) => update("email", event.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="phone">
            Phone
          </label>
          <input
            id="phone"
            value={editor.phone}
            onChange={(event) => update("phone", event.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="company">
          Company
        </label>
        <input
          id="company"
          value={editor.company}
          onChange={(event) => update("company", event.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="status">
            Status
          </label>
          <select
            id="status"
            value={editor.status}
            onChange={(event) =>
              update("status", event.target.value as Exclude<LeadStatusUi, "all">)
            }
            className="erp-input w-full px-3 py-2 text-sm"
          >
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="converted">Converted</option>
            <option value="lost">Lost</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="source">
            Source
          </label>
          <input
            id="source"
            value={editor.source}
            onChange={(event) => update("source", event.target.value)}
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-on-surface-variant" htmlFor="notes">
          Notes
        </label>
        <textarea
          id="notes"
          rows={4}
          value={editor.notes}
          onChange={(event) => update("notes", event.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>

      <button
        type="button"
        className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60"
        onClick={onSubmit}
        disabled={disabled}
      >
        {submitLabel}
      </button>
    </div>
  );
}


