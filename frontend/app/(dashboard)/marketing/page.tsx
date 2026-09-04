"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";

interface BlogPostItem {
    id: string;
    title: string;
    status: string;
    slug: string;
    updated_at: string;
}

interface BlogPostListResponse {
    items: BlogPostItem[];
}

const cards = [
    {
        title: "Social Planner",
        description: "Queue content, drafts, and publishing windows across channels.",
        icon: "calendar_month",
        accent: "bg-blue-500/15 text-blue-300",
        href: "/marketing/social",
    },
    {
        title: "Blog & Article Templates",
        description: "Generate editorial outlines, article briefs, and reusable content blocks.",
        icon: "article",
        accent: "bg-violet-500/15 text-violet-300",
        href: "/marketing/blog",
    },
    {
        title: "Campaign Builder",
        description: "Track launches, audience segments, funnel stages, and campaign performance.",
        icon: "rocket_launch",
        accent: "bg-emerald-500/15 text-emerald-300",
        href: "/marketing/campaigns",
    },
    {
        title: "AI Content Studio",
        description: "Draft social captions, blog headings, and marketing copy from campaign goals.",
        icon: "auto_awesome",
        accent: "bg-amber-500/15 text-amber-300",
        href: "/chat",
    },
];

const defaultQueue = [
    { channel: "LinkedIn", item: "Case study launch", status: "Scheduled" },
    { channel: "Instagram", item: "Customer story carousel", status: "Drafting" },
    { channel: "Email", item: "Newsletter feature", status: "Ready" },
    { channel: "YouTube", item: "Product walkthrough", status: "Review" },
];

export default function MarketingPage() {
    const [posts, setPosts] = useState<BlogPostItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = getStoredToken();
        apiRequest<BlogPostListResponse>("/api/v1/marketing/cms/blog", { authToken: token })
            .then((response) => setPosts(response.items ?? []))
            .catch(() => setPosts([]))
            .finally(() => setLoading(false));
    }, []);

    const kpis = useMemo(() => [
        { label: "Reach", value: posts.length > 0 ? `${Math.max(42, posts.length * 20)}K` : "218K", change: "+24%" },
        { label: "Engagement", value: posts.length > 0 ? "8.1%" : "7.4%", change: "+1.1 pts" },
        { label: "Conversion", value: posts.length > 0 ? "4.2%" : "3.9%", change: "+0.6 pts" },
        { label: "Pipeline", value: posts.length > 0 ? `R ${(posts.length * 125).toString()}K` : "R 892K", change: "+18%" },
    ], [posts]);

    const queue = useMemo(() => {
        if (posts.length === 0) return defaultQueue;
        return posts.slice(0, 4).map((post, index) => ({
            channel: ["LinkedIn", "Instagram", "Email", "YouTube"][index % 4],
            item: post.title,
            status: post.status === "published" ? "Published" : post.status === "draft" ? "Drafting" : "Scheduled",
        }));
    }, [posts]);

    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Marketing"
                subtitle="Social publishing, campaign planning, and content operations in one place"
            />

            {loading && (
                <div className="erp-panel p-4 text-sm text-on-surface-variant">Loading marketing data…</div>
            )}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {cards.map((card) => (
                    <Link key={card.title} href={card.href} className="erp-panel group flex flex-col gap-4 p-5 transition-colors hover:border-tertiary-fixed-dim/50">
                        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${card.accent}`}>
                            <span className="material-symbols-outlined text-xl">{card.icon}</span>
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-surface-bright group-hover:text-tertiary-fixed-dim">{card.title}</h3>
                            <p className="mt-2 text-sm text-on-surface-variant">{card.description}</p>
                        </div>
                        <span className="text-xs font-semibold text-brand">Open workspace →</span>
                    </Link>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {kpis.map((item) => (
                    <div key={item.label} className="erp-panel p-4">
                        <p className="text-sm text-on-surface-variant">{item.label}</p>
                        <p className="mt-2 text-3xl font-bold text-surface-bright">{item.value}</p>
                        <p className="mt-2 text-xs text-emerald-300">{item.change}</p>
                    </div>
                ))}
            </div>

            <div className="erp-panel p-5">
                <h2 className="text-lg font-semibold text-surface-bright">Publishing queue</h2>
                <div className="mt-4 space-y-3">
                    {queue.map((entry) => (
                        <div key={`${entry.channel}-${entry.item}`} className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container p-3">
                            <div>
                                <p className="font-medium text-surface-bright">{entry.channel}</p>
                                <p className="text-xs text-on-surface-variant">{entry.item}</p>
                            </div>
                            <span className="rounded-full bg-brand/15 px-2 py-1 text-[10px] font-medium text-brand">
                                {entry.status}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
