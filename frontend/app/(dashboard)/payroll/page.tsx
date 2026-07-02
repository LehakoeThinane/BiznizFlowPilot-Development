"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

interface PayslipOut {
  id: string;
  employee_name: string;
  gross_pay: number;
  total_deductions: number;
  net_pay: number;
  tax_deduction: number;
  uif_deduction: number;
  status: string;
}

interface PayrollPeriodOut {
  id: string;
  period_year: number;
  period_month: number;
  status: string;
  total_gross: number;
  total_deductions: number;
  total_net: number;
  processed_at: string | null;
  payslips: PayslipOut[];
}

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency: "ZAR", maximumFractionDigits: 0,
  }).format(n);
}

function statusBadge(s: string) {
  if (s === "approved") return "bg-emerald-500/20 text-emerald-300";
  if (s === "draft")    return "bg-orange-500/20 text-orange-300";
  return "bg-white/10 text-slate-300";
}

export default function PayrollPage() {
  const [periods, setPeriods] = useState<PayrollPeriodOut[]>([]);
  const [selected, setSelected] = useState<PayrollPeriodOut | null>(null);
  const [loading, setLoading] = useState(true);

  function loadPeriod(id: string) {
    setLoading(true);
    apiRequest<PayrollPeriodOut>(`/api/v1/hr/payroll/${id}`)
      .then(setSelected)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    apiRequest<PayrollPeriodOut[]>("/api/v1/hr/payroll")
      .then((d) => {
        setPeriods(d);
        if (d.length > 0) loadPeriod(d[0].id);
        else setLoading(false);
      })
      .catch(console.error);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader title="Payroll" subtitle="Monthly payroll periods" />

      <div className="flex gap-6">
        <div className="w-52 shrink-0 rounded-xl border border-white/6 bg-[#1e293b]">
          <div className="border-b border-white/6 px-4 py-3">
            <p className="text-xs font-semibold text-slate-400">Periods</p>
          </div>
          {periods.length === 0 ? (
            <p className="px-4 py-6 text-xs text-slate-500">No payroll generated yet.</p>
          ) : (
            <div className="divide-y divide-white/4">
              {periods.map((p) => (
                <button
                  type="button"
                  key={p.id}
                  onClick={() => loadPeriod(p.id)}
                  className={`w-full px-4 py-3 text-left transition-colors hover:bg-white/4 ${selected?.id === p.id ? "bg-white/6" : ""}`}
                >
                  <p className="text-sm font-medium text-white">
                    {MONTHS[p.period_month - 1]} {p.period_year}
                  </p>
                  <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${statusBadge(p.status)}`}>
                    {p.status}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1">
          {loading ? (
            <div className="text-sm text-slate-400">Loading…</div>
          ) : !selected ? (
            <div className="rounded-xl border border-white/6 bg-[#1e293b] p-8 text-center text-sm text-slate-500">
              Select a payroll period to view details.
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-3 gap-4">
                {[
                  { label: "Total Gross",       value: fmt(selected.total_gross),       color: "bg-blue-500" },
                  { label: "Total Deductions",  value: fmt(selected.total_deductions),  color: "bg-rose-500" },
                  { label: "Total Net Pay",     value: fmt(selected.total_net),         color: "bg-emerald-500" },
                ].map((c) => (
                  <div key={c.label} className="relative overflow-hidden rounded-xl border border-white/6 bg-[#1e293b] p-4">
                    <div className={`absolute left-0 top-0 h-full w-1 ${c.color}`} />
                    <p className="text-xs text-slate-400">{c.label}</p>
                    <p className="mt-1 text-xl font-bold text-white">{c.value}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-white/6 bg-[#1e293b]">
                <div className="border-b border-white/6 px-5 py-3">
                  <p className="text-sm font-semibold text-slate-300">
                    Payslips — {selected.payslips.length} employees
                  </p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/4 text-left text-xs text-slate-500">
                      <th className="px-5 py-2.5 font-medium">Employee</th>
                      <th className="px-3 py-2.5 text-right font-medium">Gross</th>
                      <th className="px-3 py-2.5 text-right font-medium">PAYE</th>
                      <th className="px-3 py-2.5 text-right font-medium">UIF</th>
                      <th className="px-3 py-2.5 text-right font-medium">Net Pay</th>
                      <th className="px-5 py-2.5 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/4">
                    {selected.payslips.map((slip) => (
                      <tr key={slip.id} className="hover:bg-white/2">
                        <td className="px-5 py-3 font-medium text-white">{slip.employee_name}</td>
                        <td className="px-3 py-3 text-right text-slate-400">{fmt(Number(slip.gross_pay))}</td>
                        <td className="px-3 py-3 text-right text-rose-400">{fmt(Number(slip.tax_deduction))}</td>
                        <td className="px-3 py-3 text-right text-rose-400">{fmt(Number(slip.uif_deduction))}</td>
                        <td className="px-3 py-3 text-right font-medium text-emerald-400">{fmt(Number(slip.net_pay))}</td>
                        <td className="px-5 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusBadge(slip.status)}`}>
                            {slip.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
