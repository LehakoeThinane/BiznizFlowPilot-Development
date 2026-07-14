"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCurrentUser } from "@/lib/auth";
import type { UserRole } from "@/types/api";

interface AppCard {
  title: string;
  description: string;
  href: string;
  icon: string;
  accent: string;
  roles: UserRole[];
}

interface Section {
  label: string;
  apps: AppCard[];
}

const SECTIONS: Section[] = [
  {
    label: "OPERATIONS",
    apps: [
      {
        title: "Finance",
        description: "Manage company ledgers, tax filings, and liquidity tracking.",
        href: "/finance",
        icon: "payments",
        accent: "bg-tertiary/20",
        roles: ["owner", "manager"],
      },
      {
        title: "HR",
        description: "Employee directories, contracts, and performance reviews.",
        href: "/employees",
        icon: "groups",
        accent: "bg-primary/20",
        roles: ["owner", "manager"],
      },
      {
        title: "Leave",
        description: "Request and approve time off with team visibility calendars.",
        href: "/leave",
        icon: "event_available",
        accent: "bg-orange-500/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Payroll",
        description: "Automated salary disbursements and slip generation.",
        href: "/payroll",
        icon: "account_balance",
        accent: "bg-emerald-700/20",
        roles: ["owner", "manager"],
      },
    ],
  },
  {
    label: "SALES & CRM",
    apps: [
      {
        title: "Invoices",
        description: "Professional billing and automated payment reminders.",
        href: "/invoices",
        icon: "receipt_long",
        accent: "bg-orange-400/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Leads",
        description: "Pipeline management and prospect communication tracking.",
        href: "/leads",
        icon: "track_changes",
        accent: "bg-blue-500/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Sales Orders",
        description: "Convert quotes to orders and track fulfillment status.",
        href: "/sales-orders",
        icon: "trending_up",
        accent: "bg-violet-500/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Purchase Orders",
        description: "Procurement workflow and vendor invoice matching.",
        href: "/purchase-orders",
        icon: "shopping_cart",
        accent: "bg-yellow-500/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Purchase Requisitions",
        description: "Request a purchase and route it for manager approval.",
        href: "/purchase-requisitions",
        icon: "fact_check",
        accent: "bg-teal-500/20",
        roles: ["owner", "manager", "staff"],
      },
    ],
  },
  {
    label: "INVENTORY & SUPPLY",
    apps: [
      {
        title: "Products",
        description: "Master catalog for SKUs, pricing, and variants.",
        href: "/products",
        icon: "inventory_2",
        accent: "bg-blue-400/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Inventory",
        description: "Real-time stock levels, warehouse bins, and reordering.",
        href: "/inventory",
        icon: "warehouse",
        accent: "bg-yellow-400/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Suppliers",
        description: "Database of vendors, quality ratings, and lead times.",
        href: "/suppliers",
        icon: "handshake",
        accent: "bg-emerald-500/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Tasks",
        description: "Operational to-do lists and project milestones.",
        href: "/tasks",
        icon: "task_alt",
        accent: "bg-orange-500/20",
        roles: ["owner", "manager", "staff"],
      },
    ],
  },
  {
    label: "SYSTEM",
    apps: [
      {
        title: "Analytics",
        description: "Deep-dive BI dashboards and custom data reporting.",
        href: "/dashboard",
        icon: "analytics",
        accent: "bg-blue-600/20",
        roles: ["owner", "manager"],
      },
      {
        title: "Workflows",
        description: "Visual automation builder for cross-app processes.",
        href: "/workflows",
        icon: "account_tree",
        accent: "bg-orange-600/20",
        roles: ["owner", "manager"],
      },
      {
        title: "AI Assistant",
        description: "Intelligent queries and predictive business insights.",
        href: "/chat",
        icon: "auto_awesome",
        accent: "bg-violet-600/20",
        roles: ["owner", "manager", "staff"],
      },
      {
        title: "Workflow Runs",
        description: "Audit logs and execution status for all active automations.",
        href: "/runs",
        icon: "bolt",
        accent: "bg-yellow-600/20",
        roles: ["owner", "manager"],
      },
    ],
  },
];

export default function HomePage() {
  const [firstName, setFirstName] = useState("");
  const [role, setRole] = useState<UserRole | null>(null);

  useEffect(() => {
    getCurrentUser()
      .then((u) => {
        setFirstName(u.full_name?.split(" ")[0] ?? u.email ?? "");
        setRole(u.role);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="-m-6 min-h-[calc(100vh-3rem)] px-8 py-8">

      {/* Status badge */}
      <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary-fixed-dim/30 bg-primary-container/60 px-3 py-1.5">
        <span className="h-2 w-2 animate-pulse rounded-full bg-tertiary-fixed-dim" />
        <span className="text-[10px] font-semibold tracking-widest text-primary-fixed-dim">
          ALL SYSTEMS OPERATIONAL
        </span>
      </div>

      {/* Heading */}
      <h1 className="text-[32px] font-bold leading-tight tracking-tight text-surface-bright">
        Welcome back{firstName ? `, ${firstName}` : ""}
      </h1>
      <p className="mt-1 text-sm text-on-surface-variant">Select an app below to get started</p>

      {/* Sections */}
      <div className="mt-10 space-y-10">
        {SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="mb-5 text-[11px] font-semibold tracking-widest text-on-surface-variant">
              {section.label}
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {section.apps
                .filter((app) => app.roles.includes(role ?? "staff"))
                .map((app) => (
                <div
                  key={app.title}
                  className="group erp-panel flex h-full flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-primary-fixed-dim/50"
                >
                  {/* Icon + LIVE badge */}
                  <div className="flex items-start justify-between">
                    <div className="glow-badge h-11 w-11">
                      <span className="material-symbols-outlined ms-28 text-tertiary-fixed-dim">
                        {app.icon}
                      </span>
                    </div>
                    <span className="rounded-full border border-tertiary-fixed-dim/20 bg-tertiary-fixed-dim/10 px-2 py-0.5 text-[10px] font-bold text-tertiary-fixed-dim">
                      LIVE
                    </span>
                  </div>

                  {/* Title + description */}
                  <p className="mt-4 text-[15px] font-semibold text-surface-bright">{app.title}</p>
                  <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-on-surface-variant">
                    {app.description}
                  </p>

                  {/* Launch */}
                  <Link
                    href={app.href}
                    className="erp-button-primary mt-5 flex w-full items-center justify-center py-2 text-sm font-semibold transition-colors"
                  >
                    Launch
                  </Link>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
