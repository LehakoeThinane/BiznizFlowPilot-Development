"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { label: "Inventory", href: "/inventory" },
  { label: "Products", href: "/products" },
  { label: "Suppliers", href: "/suppliers" },
];

/** Sub-navigation shown on every page inside the "Inventory" hub, so
 * switching between Inventory/Products/Suppliers doesn't require going back
 * to the Home page's tile grid first. */
export function InventorySubNav() {
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
