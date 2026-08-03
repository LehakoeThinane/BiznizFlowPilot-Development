"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { HRSubNav } from "@/components/HRSubNav";

interface PayComponentType {
  id: string;
  name: string;
  calculation: "fixed_amount" | "percent_of_gross";
  default_amount: number | null;
  is_active: boolean;
}

interface EmployeeDeductionOut {
  id: string; employee_id: string; employee_name: string;
  deduction_type_id: string; deduction_type_name: string;
  amount_override: number | null; is_active: boolean;
}
interface EmployeeBenefitOut {
  id: string; employee_id: string; employee_name: string;
  benefit_type_id: string; benefit_type_name: string;
  amount_override: number | null; is_active: boolean;
}

interface Employee { id: string; full_name: string }
interface EmployeeListResponse { items: Employee[]; total: number }

const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;

function fmt(v: PayComponentType) {
  if (v.default_amount == null) return "—";
  return v.calculation === "percent_of_gross"
    ? `${v.default_amount}% of gross`
    : new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(v.default_amount);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-400">{label}</label>
      {children}
    </div>
  );
}

function XIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

interface TypeForm { name: string; calculation: "fixed_amount" | "percent_of_gross"; default_amount: string }
const EMPTY_TYPE_FORM: TypeForm = { name: "", calculation: "fixed_amount", default_amount: "" };

function TypeCatalogPanel({
  title, types, onCreate, kind,
}: {
  title: string;
  types: PayComponentType[];
  kind: "deduction" | "benefit";
  onCreate: (form: TypeForm) => Promise<void>;
}) {
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<TypeForm>(EMPTY_TYPE_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onCreate(form);
      setShowModal(false);
      setForm(EMPTY_TYPE_FORM);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="erp-panel flex flex-col">
      <div className="flex items-center justify-between border-b border-white/6 px-5 py-3">
        <p className="text-sm font-semibold text-slate-300">{title}</p>
        <button
          type="button"
          onClick={() => { setShowModal(true); setForm(EMPTY_TYPE_FORM); setError(""); }}
          className="erp-button-primary px-3 py-1.5 text-xs font-medium transition-colors"
        >
          + Add
        </button>
      </div>
      {types.length === 0 ? (
        <p className="px-5 py-6 text-xs text-slate-500">None configured yet.</p>
      ) : (
        <div className="divide-y divide-white/4">
          {types.map((t) => (
            <div key={t.id} className="flex items-center justify-between px-5 py-3">
              <span className="text-sm text-white">{t.name}</span>
              <span className="text-xs text-slate-400">{fmt(t)}</span>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">New {kind === "deduction" ? "Deduction" : "Benefit"} Type</h2>
              <button type="button" aria-label="Close" onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <XIcon />
              </button>
            </div>
            <form onSubmit={submit}>
              <div className="space-y-4 px-6 py-5">
                {error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{error}</p>}
                <Field label="Name">
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    className={INPUT}
                  />
                </Field>
                <Field label="Calculation">
                  <select
                    value={form.calculation}
                    onChange={(e) => setForm((f) => ({ ...f, calculation: e.target.value as TypeForm["calculation"] }))}
                    className={SELECT}
                  >
                    <option value="fixed_amount">Fixed amount</option>
                    <option value="percent_of_gross">Percent of gross</option>
                  </select>
                </Field>
                <Field label={form.calculation === "percent_of_gross" ? "Default percentage" : "Default amount (optional)"}>
                  <input
                    type="number" step="0.01"
                    value={form.default_amount}
                    onChange={(e) => setForm((f) => ({ ...f, default_amount: e.target.value }))}
                    className={INPUT}
                  />
                </Field>
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={saving} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CompensationPage() {
  const [deductionTypes, setDeductionTypes] = useState<PayComponentType[]>([]);
  const [benefitTypes, setBenefitTypes] = useState<PayComponentType[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [employeeDeductions, setEmployeeDeductions] = useState<EmployeeDeductionOut[]>([]);
  const [employeeBenefits, setEmployeeBenefits] = useState<EmployeeBenefitOut[]>([]);

  const [assignDeductionTypeId, setAssignDeductionTypeId] = useState("");
  const [assignDeductionOverride, setAssignDeductionOverride] = useState("");
  const [assignBenefitTypeId, setAssignBenefitTypeId] = useState("");
  const [assignBenefitOverride, setAssignBenefitOverride] = useState("");

  const loadTypes = useCallback(() => {
    apiRequest<PayComponentType[]>("/api/v1/hr/deduction-types").then(setDeductionTypes).catch(console.error);
    apiRequest<PayComponentType[]>("/api/v1/hr/benefit-types").then(setBenefitTypes).catch(console.error);
  }, []);

  const loadAssignments = useCallback((employeeId: string) => {
    if (!employeeId) { setEmployeeDeductions([]); setEmployeeBenefits([]); return; }
    apiRequest<EmployeeDeductionOut[]>("/api/v1/hr/employee-deductions", { query: { employee_id: employeeId } })
      .then(setEmployeeDeductions).catch(console.error);
    apiRequest<EmployeeBenefitOut[]>("/api/v1/hr/employee-benefits", { query: { employee_id: employeeId } })
      .then(setEmployeeBenefits).catch(console.error);
  }, []);

  useEffect(() => {
    loadTypes();
    apiRequest<EmployeeListResponse>("/api/v1/hr/employees?skip=0&limit=1000")
      .then((d) => setEmployees(d.items ?? []))
      .catch(console.error);
  }, [loadTypes]);

  useEffect(() => { loadAssignments(selectedEmployee); }, [selectedEmployee, loadAssignments]);

  async function assignDeduction() {
    if (!selectedEmployee || !assignDeductionTypeId) return;
    await apiRequest("/api/v1/hr/employee-deductions", {
      method: "POST",
      body: {
        employee_id: selectedEmployee,
        deduction_type_id: assignDeductionTypeId,
        amount_override: assignDeductionOverride ? Number(assignDeductionOverride) : null,
      },
    });
    setAssignDeductionTypeId("");
    setAssignDeductionOverride("");
    loadAssignments(selectedEmployee);
  }

  async function removeDeduction(id: string) {
    await apiRequest(`/api/v1/hr/employee-deductions/${id}`, { method: "DELETE" });
    loadAssignments(selectedEmployee);
  }

  async function assignBenefit() {
    if (!selectedEmployee || !assignBenefitTypeId) return;
    await apiRequest("/api/v1/hr/employee-benefits", {
      method: "POST",
      body: {
        employee_id: selectedEmployee,
        benefit_type_id: assignBenefitTypeId,
        amount_override: assignBenefitOverride ? Number(assignBenefitOverride) : null,
      },
    });
    setAssignBenefitTypeId("");
    setAssignBenefitOverride("");
    loadAssignments(selectedEmployee);
  }

  async function removeBenefit(id: string) {
    await apiRequest(`/api/v1/hr/employee-benefits/${id}`, { method: "DELETE" });
    loadAssignments(selectedEmployee);
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      <PageHeader title="Compensation & Benefits" subtitle="Deduction and benefit types, and per-employee assignments" />

      <div className="grid grid-cols-2 gap-4">
        <TypeCatalogPanel
          title="Deduction Types"
          kind="deduction"
          types={deductionTypes}
          onCreate={async (form) => {
            await apiRequest("/api/v1/hr/deduction-types", {
              method: "POST",
              body: { name: form.name, calculation: form.calculation, default_amount: form.default_amount ? Number(form.default_amount) : null },
            });
            loadTypes();
          }}
        />
        <TypeCatalogPanel
          title="Benefit Types"
          kind="benefit"
          types={benefitTypes}
          onCreate={async (form) => {
            await apiRequest("/api/v1/hr/benefit-types", {
              method: "POST",
              body: { name: form.name, calculation: form.calculation, default_amount: form.default_amount ? Number(form.default_amount) : null },
            });
            loadTypes();
          }}
        />
      </div>

      <div className="erp-panel">
        <div className="border-b border-white/6 px-5 py-3">
          <p className="text-sm font-semibold text-slate-300">Employee Assignments</p>
        </div>
        <div className="px-5 py-4">
          <Field label="Employee">
            <select value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)} className={SELECT}>
              <option value="">Select an employee…</option>
              {employees.map((e) => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </Field>
        </div>

        {selectedEmployee && (
          <div className="grid grid-cols-2 gap-4 px-5 pb-5">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Deductions</p>
              <div className="mb-3 flex flex-col gap-2">
                {employeeDeductions.map((d) => (
                  <div key={d.id} className="flex items-center justify-between rounded-lg bg-white/4 px-3 py-2 text-sm">
                    <span className="text-white">{d.deduction_type_name}{d.amount_override != null ? ` (R${d.amount_override})` : ""}</span>
                    <button type="button" onClick={() => removeDeduction(d.id)} className="text-slate-400 hover:text-rose-400">
                      <XIcon />
                    </button>
                  </div>
                ))}
                {employeeDeductions.length === 0 && <p className="text-xs text-slate-500">No deductions assigned.</p>}
              </div>
              <div className="flex gap-2">
                <select value={assignDeductionTypeId} onChange={(e) => setAssignDeductionTypeId(e.target.value)} className={SELECT}>
                  <option value="">Add deduction…</option>
                  {deductionTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <input
                  type="number" step="0.01" placeholder="Override"
                  value={assignDeductionOverride}
                  onChange={(e) => setAssignDeductionOverride(e.target.value)}
                  className={`${INPUT} w-28`}
                />
                <button type="button" onClick={assignDeduction} className="erp-button-primary px-3 py-2 text-xs font-medium transition-colors">Add</button>
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Benefits</p>
              <div className="mb-3 flex flex-col gap-2">
                {employeeBenefits.map((b) => (
                  <div key={b.id} className="flex items-center justify-between rounded-lg bg-white/4 px-3 py-2 text-sm">
                    <span className="text-white">{b.benefit_type_name}{b.amount_override != null ? ` (R${b.amount_override})` : ""}</span>
                    <button type="button" onClick={() => removeBenefit(b.id)} className="text-slate-400 hover:text-rose-400">
                      <XIcon />
                    </button>
                  </div>
                ))}
                {employeeBenefits.length === 0 && <p className="text-xs text-slate-500">No benefits assigned.</p>}
              </div>
              <div className="flex gap-2">
                <select value={assignBenefitTypeId} onChange={(e) => setAssignBenefitTypeId(e.target.value)} className={SELECT}>
                  <option value="">Add benefit…</option>
                  {benefitTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <input
                  type="number" step="0.01" placeholder="Override"
                  value={assignBenefitOverride}
                  onChange={(e) => setAssignBenefitOverride(e.target.value)}
                  className={`${INPUT} w-28`}
                />
                <button type="button" onClick={assignBenefit} className="erp-button-primary px-3 py-2 text-xs font-medium transition-colors">Add</button>
              </div>
            </div>
          </div>
        )}
      </div>

      <p className="text-xs text-slate-500">
        Benefits are tracked here for record-keeping but don&apos;t yet affect payroll calculations —
        fringe-benefit tax treatment (e.g. medical aid tax credits) is a planned enhancement.
      </p>
    </div>
  );
}
