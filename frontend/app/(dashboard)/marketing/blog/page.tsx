"use client";

import { MarketingSubNav } from "@/components/MarketingSubNav";
import { PageHeader } from "@/components/PageHeader";

const templates = [
    { name: "Thought leadership article", format: "Long-form SEO draft" },
    { name: "Case study template", format: "Problem → solution → metrics" },
    { name: "Newsletter feature", format: "3 sections + CTA" },
    { name: "Launch announcement", format: "Headline + bullets + social CTA" },
];

export default function MarketingBlogPage() {
    return (
        <div className="flex flex-col gap-6 p-6">
            <MarketingSubNav />
            <PageHeader
                title="Blog and article templates"
                subtitle="Reusable article structures for blog, editorial and lifecycle campaigns"
            />

            <div className="grid gap-4 md:grid-cols-2">
                {templates.map((template) => (
                    <div key={template.name} className="erp-panel p-5">
                        <p className="font-medium text-surface-bright">{template.name}</p>
                        <p className="mt-2 text-sm text-on-surface-variant">{template.format}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}
