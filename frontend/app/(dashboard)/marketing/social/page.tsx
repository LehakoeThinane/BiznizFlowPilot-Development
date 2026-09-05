"use client";

import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";
import { useState } from "react";

const posts = [
    { channel: "LinkedIn", post: "Share product milestone and customer proof points.", status: "Scheduled" },
    { channel: "Instagram", post: "Carousel on workflow automation wins.", status: "Drafting" },
    { channel: "X / Twitter", post: "Flash announcement with CTA to sign up.", status: "Approved" },
    { channel: "Facebook", post: "Community poll and testimonial repost.", status: "Queued" },
];

const channelDetails: Record<string, { account: string; cadence: string }> = {
    LinkedIn: { account: "Company page", cadence: "Weekdays · 09:00" },
    Instagram: { account: "Business profile", cadence: "Tue / Thu · 12:00" },
    "X / Twitter": { account: "Brand profile", cadence: "Daily · 10:30" },
    Facebook: { account: "Business page", cadence: "Wed / Fri · 14:00" },
};

export default function MarketingSocialPage() {
    const [selectedChannel, setSelectedChannel] = useState(posts[0].channel);
    const selected = channelDetails[selectedChannel];

    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Social planner"
                subtitle="Review content drafts, scheduling windows, and channel publishing status"
            />

            <div className="grid gap-4 md:grid-cols-2">
                {posts.map((item) => (
                    <button key={item.channel} type="button" onClick={() => setSelectedChannel(item.channel)} className={`erp-panel p-5 text-left transition-colors hover:border-tertiary-fixed-dim/50 ${selectedChannel === item.channel ? "border-tertiary-fixed-dim/70 shadow-[0_0_22px_rgba(45,212,190,0.16)]" : ""}`}>
                        <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-surface-bright">{item.channel}</p>
                            <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">{item.status}</span>
                        </div>
                        <p className="mt-3 text-sm text-on-surface-variant">{item.post}</p>
                        <span className="mt-4 block text-xs font-semibold text-brand">Manage channel →</span>
                    </button>
                ))}
            </div>

            <section className="erp-panel p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-on-surface-variant">Selected channel</p>
                        <h2 className="mt-2 text-xl font-semibold text-surface-bright">{selectedChannel}</h2>
                        <p className="mt-1 text-sm text-on-surface-variant">{selected.account} · {selected.cadence}</p>
                    </div>
                </div>
                <div className="mt-5 grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-on-surface-variant">Drafts</p>
                        <p className="mt-2 text-sm text-surface-bright">Review copy and attach campaign context.</p>
                    </div>
                    <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-on-surface-variant">Schedule</p>
                        <p className="mt-2 text-sm text-surface-bright">Choose a publishing window for the selected channel.</p>
                    </div>
                    <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-on-surface-variant">Approval</p>
                        <p className="mt-2 text-sm text-surface-bright">Route the post to a manager before publishing.</p>
                    </div>
                </div>
            </section>
        </div>
    );
}
