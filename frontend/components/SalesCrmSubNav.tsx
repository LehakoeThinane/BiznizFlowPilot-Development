"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { label: "Leads", href: "/leads" },
  { label: "Sales Orders", href: "/sales-orders" },
];

/** Sub-navigation shown on every page inside the "Sales & CRM" sidebar
 * section, so switching between Leads/Sales Orders doesn't require going
 * back to the Home page's tile grid first. Tasks, Invoices, and the
 * purchasing pages moved to their own hubs (Inventory & Supply / Finance /
 * Purchasing) and are no longer members of this sub-nav. */
export function SalesCrmSubNav() {
  const pathname = usePathname();

  return (
    <nav className="mb-4 flex flex-wrap gap-1 border-b border-outline-variant pb-3">
      {TABS.map((tab) => {
        const isActive = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              isActive
                ? "bg-brand text-on-primary"
                : "text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
