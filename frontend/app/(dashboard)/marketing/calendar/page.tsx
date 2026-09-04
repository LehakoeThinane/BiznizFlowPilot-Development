"use client";

import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";

const schedule = [
    { date: "Mon 8", channel: "LinkedIn", topic: "Product update", owner: "Marketing" },
    { date: "Tue 9", channel: "Instagram", topic: "Customer story", owner: "Brand" },
    { date: "Wed 10", channel: "X / Twitter", topic: "Launch teaser", owner: "Growth" },
    { date: "Thu 11", channel: "Email", topic: "Newsletter", owner: "Lifecycle" },
    { date: "Fri 12", channel: "YouTube", topic: "Tutorial video", owner: "Content" },
];

export default function MarketingCalendarPage() {
    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Content calendar"
                subtitle="Plan, sequence, and coordinate marketing activity across channels"
            />

            <div className="erp-panel p-5">
                <div className="grid gap-3 md:grid-cols-5">
                    {schedule.map((item) => (
                        <div key={`${item.date}-${item.channel}`} className="rounded-xl border border-outline-variant bg-surface-container p-4">
                            <p className="text-xs uppercase tracking-[0.12em] text-on-surface-variant">{item.date}</p>
                            <p className="mt-3 font-medium text-surface-bright">{item.channel}</p>
                            <p className="mt-1 text-sm text-on-surface-variant">{item.topic}</p>
                            <p className="mt-3 text-[11px] text-on-surface-variant">Owner: {item.owner}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
