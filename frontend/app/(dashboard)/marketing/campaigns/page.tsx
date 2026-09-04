"use client";

import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";

const campaigns = [
    { name: "Q4 lead gen sprint", status: "Running", progress: "72%" },
    { name: "Customer education wave", status: "Planning", progress: "24%" },
    { name: "Product launch push", status: "Scheduled", progress: "48%" },
    { name: "Retention winback", status: "Draft", progress: "12%" },
];

export default function MarketingCampaignsPage() {
    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Campaigns"
                subtitle="Track campaign execution, goals, and funnel progress in one workspace"
            />

            <div className="grid gap-4 md:grid-cols-2">
                {campaigns.map((campaign) => (
                    <div key={campaign.name} className="erp-panel p-5">
                        <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-surface-bright">{campaign.name}</p>
                            <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-[10px] font-medium text-emerald-300">{campaign.status}</span>
                        </div>
                        <div className="mt-4 h-2 rounded-full bg-surface-container-high">
                            <div className="h-2 rounded-full bg-brand" style={{ width: campaign.progress }} />
                        </div>
                        <p className="mt-2 text-xs text-on-surface-variant">Progress: {campaign.progress}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}
