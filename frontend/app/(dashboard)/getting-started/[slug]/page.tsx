import Link from "next/link";
import { notFound } from "next/navigation";

import { ONBOARDING_GUIDES } from "@/lib/onboarding-guides";

export default async function GettingStartedGuidePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = ONBOARDING_GUIDES[slug];
  if (!guide) notFound();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link href="/dashboard" className="text-xs font-medium text-muted hover:text-white">
        &larr; Back to dashboard
      </Link>
      <div className="erp-panel px-6 py-6">
        <h1 className="text-lg font-bold text-white">{guide.title}</h1>
        <div className="mt-4 space-y-3 text-sm text-[#ccc]">{guide.content}</div>
      </div>
    </div>
  );
}
