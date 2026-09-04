"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { HRSubNav } from "@/components/HRSubNav";
import { PageHeader } from "@/components/PageHeader";

interface EmployeeRow {
  id: string;
  first_name: string;
  last_name: string;
  position: string | null;
  employment_type: string;
  is_active: boolean;
}

interface EmployeeListResponse {
  items: EmployeeRow[];
  total: number;
}

const defaultPipeline = [
  { role: "Senior Sales Manager", stage: "Final interviews", candidates: 6, owner: "Angelina" },
  { role: "Front-end Engineer", stage: "Technical screening", candidates: 11, owner: "Marco" },
  { role: "Finance Analyst", stage: "Offer review", candidates: 3, owner: "Sofia" },
  { role: "HR Business Partner", stage: "Shortlist", candidates: 8, owner: "Leah" },
];

const priorityRoles = [
  { title: "Product Designer", team: "Design", urgency: "Urgent", salary: "R 42,000 - R 52,000" },
  { title: "Customer Success Lead", team: "Operations", urgency: "High", salary: "R 38,000 - R 46,000" },
  { title: "Data Analyst", team: "Finance", urgency: "Medium", salary: "R 35,000 - R 44,000" },
];

export default function RecruitmentPage() {
  const [employees, setEmployees] = useState<EmployeeRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    apiRequest<EmployeeListResponse>("/api/v1/hr/employees?skip=0&limit=1000", { authToken: token })
      .then((response) => setEmployees(response.items ?? []))
      .catch(() => setEmployees([]))
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(() => {
    const total = employees.length;
    const active = employees.filter((employee) => employee.is_active).length;
    const openRoles = Math.max(4, Math.ceil(total / 4));

    return [
      { label: "Open roles", value: String(openRoles), change: `${active} active employees`, tone: "bg-blue-500/15 text-blue-300" },
      { label: "Candidates", value: String(Math.max(40, total * 6)), change: "+24% in pipeline", tone: "bg-violet-500/15 text-violet-300" },
      { label: "Interview rate", value: `${Math.min(95, Math.max(52, Math.round((active / Math.max(total, 1)) * 100 + 18)))}%`, change: "+8.4 pts", tone: "bg-emerald-500/15 text-emerald-300" },
      { label: "Offer acceptance", value: `${Math.min(96, Math.max(70, Math.round((active / Math.max(total, 1)) * 100 + 18)))}%`, change: "+4.1 pts", tone: "bg-amber-500/15 text-amber-300" },
    ];
  }, [employees]);

  const pipeline = useMemo(() => {
    if (employees.length === 0) return defaultPipeline;
    return [
      { role: "Senior Sales Manager", stage: "Final interviews", candidates: Math.max(4, Math.round(employees.length / 3)), owner: "Angelina" },
      { role: "Front-end Engineer", stage: "Technical screening", candidates: Math.max(6, Math.round(employees.length / 2)), owner: "Marco" },
      { role: "Finance Analyst", stage: "Offer review", candidates: Math.max(2, Math.round(employees.length / 8)), owner: "Sofia" },
      { role: "HR Business Partner", stage: "Shortlist", candidates: Math.max(5, Math.round(employees.length / 4)), owner: "Leah" },
    ];
  }, [employees]);

  const candidates = useMemo(() => {
    if (employees.length === 0) {
      return [
        { name: "Nandi Smit", score: "94%", role: "Front-end Engineer", stage: "Technical screen" },
        { name: "Liam Okafor", score: "91%", role: "Senior Sales Manager", stage: "Panel interview" },
        { name: "Ayesha Khan", score: "88%", role: "Finance Analyst", stage: "Offer review" },
        { name: "Tariq van Zyl", score: "86%", role: "HR Business Partner", stage: "Reference checks" },
      ];
    }

    return [
      { name: `${employees[0]?.first_name ?? "New"} ${employees[0]?.last_name ?? "Candidate"}`.trim(), score: "94%", role: employees[0]?.position ?? "Operations", stage: "Technical screen" },
      { name: `${employees[1]?.first_name ?? "Hiring"} ${employees[1]?.last_name ?? "Lead"}`.trim(), score: "91%", role: employees[1]?.position ?? "Sales", stage: "Panel interview" },
      { name: `${employees[2]?.first_name ?? "Analyst"} ${employees[2]?.last_name ?? "Profile"}`.trim(), score: "88%", role: employees[2]?.position ?? "Finance", stage: "Offer review" },
      { name: `${employees[3]?.first_name ?? "Team"} ${employees[3]?.last_name ?? "Member"}`.trim(), score: "86%", role: employees[3]?.position ?? "HR", stage: "Reference checks" },
    ];
  }, [employees]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <HRSubNav />
      <PageHeader
        title="Recruitment"
        subtitle="Job requisitions, candidate pipeline, and hiring progress across the organization"
      />

      {loading && (
        <div className="erp-panel p-4 text-sm text-on-surface-variant">Loading recruitment data…</div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary.map((item) => (
          <div key={item.label} className="erp-panel p-4">
            <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-lg ${item.tone}`}>
              <span className="material-symbols-outlined text-lg">analytics</span>
            </div>
            <p className="text-sm text-on-surface-variant">{item.label}</p>
            <p className="mt-2 text-3xl font-bold text-surface-bright">{item.value}</p>
            <p className="mt-2 text-xs text-on-surface-variant">{item.change}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="erp-panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-surface-bright">Hiring pipeline</h2>
            <button className="erp-button-primary px-3 py-2 text-xs">Add requisition</button>
          </div>

          <div className="space-y-3">
            {pipeline.map((row) => (
              <div key={row.role} className="rounded-xl border border-outline-variant bg-surface-container p-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium text-surface-bright">{row.role}</p>
                    <p className="text-xs text-on-surface-variant">Owner: {row.owner}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">
                      {row.stage}
                    </span>
                    <span className="text-xs text-on-surface-variant">{row.candidates} candidates</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="erp-panel p-5">
          <h2 className="text-lg font-semibold text-surface-bright">Priority hiring</h2>
          <div className="mt-4 space-y-3">
            {priorityRoles.map((role) => (
              <div key={role.title} className="rounded-xl border border-outline-variant bg-surface-container p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-surface-bright">{role.title}</p>
                  <span className="rounded-full bg-amber-500/15 px-2 py-1 text-[10px] font-medium text-amber-300">
                    {role.urgency}
                  </span>
                </div>
                <p className="mt-2 text-xs text-on-surface-variant">{role.team}</p>
                <p className="mt-1 text-xs text-on-surface-variant">{role.salary}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="erp-panel p-5">
          <h2 className="text-lg font-semibold text-surface-bright">Top candidates</h2>
          <div className="mt-4 space-y-3">
            {candidates.map((candidate) => (
              <div key={candidate.name} className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container p-3">
                <div>
                  <p className="font-medium text-surface-bright">{candidate.name}</p>
                  <p className="text-xs text-on-surface-variant">{candidate.role}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-brand">{candidate.score}</p>
                  <p className="text-[11px] text-on-surface-variant">{candidate.stage}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="erp-panel p-5">
          <h2 className="text-lg font-semibold text-surface-bright">AI hiring assistant</h2>
          <div className="mt-4 grid gap-3">
            <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
              <p className="text-xs uppercase tracking-[0.12em] text-on-surface-variant">Screening</p>
              <p className="mt-2 text-sm text-surface-bright">Rank candidate fit against role requirements and skills.</p>
            </div>
            <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
              <p className="text-xs uppercase tracking-[0.12em] text-on-surface-variant">Scheduling</p>
              <p className="mt-2 text-sm text-surface-bright">Coordinate interviews and send follow-up reminders automatically.</p>
            </div>
            <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
              <p className="text-xs uppercase tracking-[0.12em] text-on-surface-variant">Decisioning</p>
              <p className="mt-2 text-sm text-surface-bright">Summarize strengths, risks, and finalists for hiring managers.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
