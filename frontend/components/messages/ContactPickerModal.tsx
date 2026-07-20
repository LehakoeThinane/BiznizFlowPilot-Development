"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Customer, CustomerListResponse } from "@/types/api";

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

export function ContactPickerModal({
  token,
  onSelect,
  onClose,
}: {
  token: string | null;
  onSelect: (customer: Customer) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      apiRequest<CustomerListResponse>("/api/v1/customers", {
        authToken: token,
        query: { name: search || undefined, limit: 30 },
      })
        .then((d) => setCustomers(d.items ?? []))
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(timer);
  }, [search, token]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Share a contact</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
        <div className="px-4 pt-3">
          <input
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customers…"
            className="erp-input w-full px-3 py-2 text-sm"
          />
        </div>
        <div className="max-h-80 overflow-y-auto py-2">
          {loading ? (
            <div className="px-6 py-8 text-center text-xs text-slate-500">Loading…</div>
          ) : customers.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-slate-500">No customers found.</p>
          ) : (
            customers.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  onSelect(c);
                  onClose();
                }}
                className="flex w-full items-center gap-3 px-6 py-2.5 text-left transition-colors hover:bg-white/5"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-600 text-xs font-semibold text-white">
                  {initials(c.name)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-white">{c.name}</p>
                  <p className="truncate text-xs text-slate-500">{c.phone || c.email || c.company || ""}</p>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
