"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { UserRole } from "@/types/api";

interface NavItem {
  label: string;
  icon: string;
  href: string;
  matches: string[];
  roles: UserRole[];
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    icon: "dashboard",
    href: "/home",
    matches: ["/home", "/chat"],
    roles: ["owner", "manager", "staff"],
  },
  {
    label: "Operations",
    icon: "settings_applications",
    href: "/employees",
    matches: ["/employees", "/leave", "/payroll"],
    roles: ["owner", "manager"],
  },
  {
    label: "Calendar",
    icon: "calendar_month",
    href: "/calendar",
    matches: ["/calendar"],
    roles: ["owner", "manager", "staff"],
  },
  {
    label: "Sales & CRM",
    icon: "groups",
    href: "/leads",
    matches: ["/leads", "/tasks", "/invoices", "/sales-orders", "/purchase-orders"],
    roles: ["owner", "manager", "staff"],
  },
  {
    label: "Inventory",
    icon: "inventory_2",
    href: "/products",
    matches: ["/products", "/suppliers", "/inventory"],
    roles: ["owner", "manager", "staff"],
  },
  {
    label: "Finance",
    icon: "payments",
    href: "/finance",
    matches: ["/finance"],
    roles: ["owner", "manager"],
  },
  {
    label: "Reports",
    icon: "analytics",
    href: "/dashboard",
    matches: ["/dashboard", "/workflows", "/runs"],
    roles: ["owner", "manager"],
  },
  {
    label: "Activity",
    icon: "history",
    href: "/activity",
    matches: ["/activity"],
    roles: ["owner", "manager"],
  },
  {
    label: "Organization",
    icon: "corporate_fare",
    href: "/organization",
    matches: ["/organization"],
    roles: ["it_admin"],
  },
];

export function RoleMenu({ role }: { role: UserRole }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col gap-1">
      {NAV_ITEMS.filter((item) => item.roles.includes(role)).map((item) => {
        const isActive = item.matches.some(
          (m) => pathname === m || pathname.startsWith(`${m}/`)
        );

        if (isActive) {
          return (
            <Link
              key={item.href}
              href={item.href}
              className="group flex items-center gap-3 rounded-xl border border-primary-fixed-dim/40 bg-primary-container/70 px-4 py-3 text-sm text-on-primary-container shadow-sm transition-colors"
            >
              <span className="material-symbols-outlined text-primary-fixed-dim">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        }

        return (
          <Link
            key={item.href}
            href={item.href}
            className="group flex items-center gap-3 rounded-xl border border-transparent px-4 py-3 text-sm text-surface-variant transition-colors hover:border-white/10 hover:bg-white/5 hover:text-surface-bright"
          >
            <span className="material-symbols-outlined text-primary-fixed-dim/90 transition-transform group-hover:scale-105">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
}
