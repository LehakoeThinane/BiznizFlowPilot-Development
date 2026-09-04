"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { apiRequest } from "@/lib/api";

type CountResponse = { total?: number; items?: unknown[] };

const supportAreas = [
    { title: "Customer conversations", description: "Continue a customer conversation, share context, and coordinate a response.", href: "/messages", icon: "chat" },
    { title: "Customer records", description: "Open customer history, contacts, and account information before responding.", href: "/customers", icon: "person" },
    { title: "Service follow-up", description: "Create and track internal work assigned to the team.", href: "/tasks", icon: "task_alt" },
    { title: "Meetings and calls", description: "Schedule a customer meeting or start a voice and video call.", href: "/calendar", icon: "calendar_month" },
];

export default function SupportPage() {
    const [customerCount, setCustomerCount] = useState<number | null>(null);
    const [taskCount, setTaskCount] = useState<number | null>(null);

    useEffect(() => {
        Promise.all([
            apiRequest<CountResponse>("/api/v1/customers?limit=1"),
            apiRequest<CountResponse>("/api/v1/tasks?limit=1"),
        ]).then(([customers, tasks]) => {
            setCustomerCount(customers.total ?? customers.items?.length ?? 0);
            setTaskCount(tasks.total ?? tasks.items?.length ?? 0);
        }).catch(() => {
            setCustomerCount(null);
            setTaskCount(null);
        });
    }, []);

    return (
        <div className="flex flex-col gap-6 p-6">
            <PageHeader
                title="Customer Support"
                subtitle="Coordinate customer conversations, service follow-up, and account context from the ERP"
            />

            <div className="grid gap-4 md:grid-cols-3">
                <div className="erp-panel p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-on-surface-variant">Customer accounts</p>
                    <p className="mt-2 text-3xl font-bold text-surface-bright">{customerCount ?? "—"}</p>
                    <p className="mt-1 text-xs text-on-surface-variant">Available customer records</p>
                </div>
                <div className="erp-panel p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-on-surface-variant">Service work</p>
                    <p className="mt-2 text-3xl font-bold text-surface-bright">{taskCount ?? "—"}</p>
                    <p className="mt-1 text-xs text-on-surface-variant">Tasks available for follow-up</p>
                </div>
                <div className="erp-panel p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-on-surface-variant">Support workspace</p>
                    <p className="mt-2 text-3xl font-bold text-brand">Connected</p>
                    <p className="mt-1 text-xs text-on-surface-variant">Uses CRM, messaging, tasks, and calendar</p>
                </div>
            </div>

            <section>
                <div className="mb-3 flex items-end justify-between gap-3">
                    <div>
                        <h2 className="text-lg font-semibold text-surface-bright">Support operations</h2>
                        <p className="mt-1 text-sm text-on-surface-variant">Choose the workspace needed to resolve the customer request.</p>
                    </div>
                    <Link href="/chat" className="erp-button-primary px-3 py-2 text-xs">Ask co-pilot</Link>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                    {supportAreas.map((area) => (
                        <Link key={area.href} href={area.href} className="erp-panel group flex items-start gap-4 p-5 transition-colors hover:border-tertiary-fixed-dim/50">
                            <span className="material-symbols-outlined rounded-xl bg-primary-container p-3 text-tertiary-fixed-dim">{area.icon}</span>
                            <span>
                                <span className="block font-semibold text-surface-bright group-hover:text-tertiary-fixed-dim">{area.title}</span>
                                <span className="mt-2 block text-sm leading-6 text-on-surface-variant">{area.description}</span>
                                <span className="mt-3 block text-xs font-semibold text-brand">Open workspace →</span>
                            </span>
                        </Link>
                    ))}
                </div>
            </section>

            <div className="rounded-xl border border-outline-variant bg-surface-container p-5 text-sm text-on-surface-variant">
                Dedicated tickets, SLAs, queues, knowledge base articles, and customer satisfaction reporting should be added as the next Support phase. This workspace intentionally uses the ERP records that already exist instead of displaying invented ticket data.
            </div>
        </div>
    );
}
