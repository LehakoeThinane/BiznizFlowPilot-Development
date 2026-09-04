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
    is_active: boolean;
    start_date: string | null;
}

interface OnboardingStepResponse {
    key: string;
    done: boolean;
}

interface OnboardingChecklistResponse {
    steps: OnboardingStepResponse[];
}

interface EmployeeListResponse {
    items: EmployeeRow[];
    total: number;
}

const fallbackSteps = [
    { name: "Offer acceptance", status: "Completed", detail: "Candidate accepted and signed required documents." },
    { name: "Pre-start compliance", status: "In progress", detail: "Identity and tax checks are awaiting review." },
    { name: "Equipment setup", status: "Scheduled", detail: "Laptop, access rights, and security credentials due this week." },
    { name: "Manager onboarding plan", status: "Pending", detail: "Department onboarding checklist still needs approval." },
];

export default function OnboardingPage() {
    const [employees, setEmployees] = useState<EmployeeRow[]>([]);
    const [steps, setSteps] = useState<OnboardingStepResponse[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = getStoredToken();

        Promise.all([
            apiRequest<EmployeeListResponse>("/api/v1/hr/employees?skip=0&limit=1000", { authToken: token }),
            apiRequest<OnboardingChecklistResponse>("/api/v1/onboarding", { authToken: token }).catch(() => ({ steps: [] })),
        ])
            .then(([employeeResponse, onboardingResponse]) => {
                setEmployees(employeeResponse.items ?? []);
                setSteps(onboardingResponse.steps ?? []);
            })
            .catch(() => {
                setEmployees([]);
                setSteps([]);
            })
            .finally(() => setLoading(false));
    }, []);

    const metrics = useMemo(() => {
        const total = employees.length;
        const active = employees.filter((employee) => employee.is_active).length;
        const ready = steps.filter((step) => step.done).length;
        const totalSteps = Math.max(1, steps.length || 4);

        return [
            { label: "New starters", value: String(total), tone: "bg-blue-500/15 text-blue-300" },
            { label: "Ready to start", value: String(Math.max(1, Math.round((ready / totalSteps) * 100))), tone: "bg-emerald-500/15 text-emerald-300" },
            { label: "At risk", value: String(Math.max(0, total - active)), tone: "bg-amber-500/15 text-amber-300" },
            { label: "Completed", value: `${Math.max(0, Math.min(100, Math.round((ready / totalSteps) * 100)))}%`, tone: "bg-violet-500/15 text-violet-300" },
        ];
    }, [employees, steps]);

    const stepCards = useMemo(() => {
        if (steps.length === 0) return fallbackSteps;
        return steps.map((step) => ({
            name: step.key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()),
            status: step.done ? "Completed" : "In progress",
            detail: step.done ? "Required step completed and ready for review." : "Checklist item still needs action before start date.",
        }));
    }, [steps]);

    const starterList = useMemo(() => {
        if (employees.length === 0) {
            return [
                { name: "Jade Pretorius", team: "Product", start: "2026-09-14", status: "Ready" },
                { name: "Mpho Ndlovu", team: "Support", start: "2026-09-16", status: "In progress" },
                { name: "Noah Jacobs", team: "Finance", start: "2026-09-20", status: "Awaiting docs" },
                { name: "Rina Patel", team: "Operations", start: "2026-09-22", status: "Scheduled" },
            ];
        }

        return employees.slice(0, 4).map((employee, index) => ({
            name: `${employee.first_name} ${employee.last_name}`.trim(),
            team: employee.position ?? "Operations",
            start: employee.start_date ?? `2026-09-${10 + index}`,
            status: employee.is_active ? "Ready" : "In progress",
        }));
    }, [employees]);

    return (
        <div className="flex flex-col gap-6 p-6">
            <HRSubNav />
            <PageHeader
                title="Onboarding"
                subtitle="Employee readiness, required actions, and manager orientation plan"
            />

            {loading && (
                <div className="erp-panel p-4 text-sm text-on-surface-variant">Loading onboarding data…</div>
            )}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {metrics.map((item) => (
                    <div key={item.label} className="erp-panel p-4">
                        <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-lg ${item.tone}`}>
                            <span className="material-symbols-outlined text-lg">task_alt</span>
                        </div>
                        <p className="text-sm text-on-surface-variant">{item.label}</p>
                        <p className="mt-2 text-3xl font-bold text-surface-bright">{item.value}</p>
                    </div>
                ))}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="erp-panel p-5">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-surface-bright">Current onboarding checklist</h2>
                        <button className="erp-button-primary px-3 py-2 text-xs">Create checklist</button>
                    </div>

                    <div className="space-y-3">
                        {stepCards.map((step) => (
                            <div key={step.name} className="rounded-xl border border-outline-variant bg-surface-container p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <p className="font-medium text-surface-bright">{step.name}</p>
                                    <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">
                                        {step.status}
                                    </span>
                                </div>
                                <p className="mt-2 text-sm text-on-surface-variant">{step.detail}</p>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="erp-panel p-5">
                    <h2 className="text-lg font-semibold text-surface-bright">AI onboarding agent</h2>
                    <div className="mt-4 space-y-3 text-sm text-on-surface-variant">
                        <div className="rounded-xl border border-outline-variant bg-surface-container p-3">
                            <p className="font-medium text-surface-bright">Checklist generation</p>
                            <p className="mt-1">Creates onboarding tasks based on department, role, and start date.</p>
                        </div>
                        <div className="rounded-xl border border-outline-variant bg-surface-container p-3">
                            <p className="font-medium text-surface-bright">Manager summary</p>
                            <p className="mt-1">Prepares a focused briefing for the new hire&apos;s first week.</p>
                        </div>
                        <div className="rounded-xl border border-outline-variant bg-surface-container p-3">
                            <p className="font-medium text-surface-bright">Compliance reminders</p>
                            <p className="mt-1">Flags missing documents, required training, and access requests.</p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="erp-panel p-5">
                <h2 className="text-lg font-semibold text-surface-bright">New starters</h2>
                <div className="mt-4 space-y-3">
                    {starterList.map((person) => (
                        <div key={person.name} className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container p-3">
                            <div>
                                <p className="font-medium text-surface-bright">{person.name}</p>
                                <p className="text-xs text-on-surface-variant">{person.team} • Start: {person.start}</p>
                            </div>
                            <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">
                                {person.status}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
