"use client";

import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";

const posts = [
    { channel: "LinkedIn", post: "Share product milestone and customer proof points.", status: "Scheduled" },
    { channel: "Instagram", post: "Carousel on workflow automation wins.", status: "Drafting" },
    { channel: "X / Twitter", post: "Flash announcement with CTA to sign up.", status: "Approved" },
    { channel: "Facebook", post: "Community poll and testimonial repost.", status: "Queued" },
];

export default function MarketingSocialPage() {
    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Social planner"
                subtitle="Review content drafts, scheduling windows, and channel publishing status"
            />

            <div className="grid gap-4 md:grid-cols-2">
                {posts.map((item) => (
                    <div key={item.channel} className="erp-panel p-5">
                        <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-surface-bright">{item.channel}</p>
                            <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">{item.status}</span>
                        </div>
                        <p className="mt-3 text-sm text-on-surface-variant">{item.post}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}
