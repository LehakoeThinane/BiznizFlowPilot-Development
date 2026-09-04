"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import type { UserRole } from "@/types/api";
import { apiRequest } from "@/lib/api";
import { playNotificationSound, unlockNotificationSound } from "@/lib/notification-sound";

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
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Finance",
    icon: "payments",
    href: "/finance",
    matches: ["/finance", "/invoices", "/payroll"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "HR",
    icon: "groups",
    href: "/employees",
    matches: ["/employees", "/leave", "/recruitment", "/onboarding", "/performance", "/compensation", "/engagement"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Invite Team",
    icon: "person_add",
    href: "/organization/invites",
    matches: ["/organization/invites"],
    roles: ["owner", "manager"],
  },
  {
    label: "Calendar",
    icon: "calendar_month",
    href: "/calendar",
    matches: ["/calendar"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Email",
    icon: "mail",
    href: "/email",
    matches: ["/email"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Messages",
    icon: "chat",
    href: "/messages",
    matches: ["/messages"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Sales & CRM",
    icon: "track_changes",
    href: "/leads",
    matches: ["/leads", "/sales-orders"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Customers",
    icon: "person",
    href: "/customers",
    matches: ["/customers"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Support",
    icon: "support_agent",
    href: "/support",
    matches: ["/support"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Purchasing",
    icon: "shopping_cart",
    href: "/purchase-orders",
    matches: ["/purchase-orders", "/purchase-requisitions"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Inventory",
    icon: "inventory_2",
    href: "/inventory",
    matches: ["/products", "/suppliers", "/inventory"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Tasks",
    icon: "task_alt",
    href: "/tasks",
    matches: ["/tasks"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Marketing",
    icon: "campaign",
    href: "/marketing",
    matches: ["/marketing", "/marketing/calendar", "/marketing/social", "/marketing/blog", "/marketing/campaigns"],
    roles: ["owner", "manager", "staff", "it_admin"],
  },
  {
    label: "Reports",
    icon: "analytics",
    href: "/dashboard",
    matches: ["/dashboard", "/workflows", "/runs"],
    roles: ["owner", "manager"],
  },
  {
    label: "Documents",
    icon: "folder",
    href: "/documents",
    matches: ["/documents"],
    roles: ["owner", "manager", "staff", "it_admin"],
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

function UnreadBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="ml-auto flex h-4.5 min-w-[1.125rem] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
      {count > 9 ? "9+" : count}
    </span>
  );
}

function navGroup(label: string): string {
  if (["Dashboard", "Finance", "Purchasing", "Inventory", "Tasks"].includes(label)) return "Operations";
  if (["HR", "Invite Team"].includes(label)) return "People";
  if (["Calendar", "Email", "Messages"].includes(label)) return "Collaboration";
  if (["Sales & CRM", "Customers", "Support"].includes(label)) return "Customer Operations";
  if (["Marketing"].includes(label)) return "Growth";
  if (["Reports", "Activity"].includes(label)) return "Automation & Reporting";
  return "Administration";
}

const NAV_GROUP_ORDER = [
  "Operations",
  "People",
  "Customer Operations",
  "Collaboration",
  "Growth",
  "Automation & Reporting",
  "Administration",
];

export function RoleMenu({ role }: { role: UserRole }) {
  const pathname = usePathname();
  const [unreadMessages, setUnreadMessages] = useState(0);
  const previousUnreadMessagesRef = useRef<number | null>(null);
  const visibleItems = NAV_ITEMS
    .filter((item) => item.roles.includes(role))
    .sort((left, right) => NAV_GROUP_ORDER.indexOf(navGroup(left.label)) - NAV_GROUP_ORDER.indexOf(navGroup(right.label)));

  const fetchUnread = useCallback(() => {
    apiRequest<{ unread_count: number }>("/api/v1/messaging/unread-count", { _skipRefresh: true })
      .then((d) => {
        if (previousUnreadMessagesRef.current !== null && d.unread_count > previousUnreadMessagesRef.current) {
          playNotificationSound();
        }
        previousUnreadMessagesRef.current = d.unread_count;
        setUnreadMessages(d.unread_count);
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    fetchUnread();
    const interval = setInterval(fetchUnread, 30_000);
    return () => clearInterval(interval);
  }, [fetchUnread]);

  return (
    <div className="flex flex-col gap-1" onClick={unlockNotificationSound}>
      {visibleItems.map((item, index) => {
        const isActive = item.matches.some(
          (m) => pathname === m || pathname.startsWith(`${m}/`)
        );
        const badge = item.href === "/messages" ? <UnreadBadge count={unreadMessages} /> : null;
        const group = navGroup(item.label);
        const previousGroup = index > 0 ? navGroup(visibleItems[index - 1].label) : null;
        const groupHeading = group !== previousGroup ? (
          <p className="mb-1 mt-4 px-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-on-surface-variant first:mt-0">{group}</p>
        ) : null;

        if (isActive) {
          return (
            <div key={item.href}>{groupHeading}<Link
              href={item.href}
              className="group flex items-center gap-3 rounded-xl border border-tertiary-fixed-dim/50 bg-primary-container/70 px-4 py-3 text-sm text-on-primary-container shadow-[0_0_0_1px_rgba(45,212,190,0.15),0_0_20px_rgba(45,212,190,0.25)] transition-shadow"
            >
              <span className="material-symbols-outlined text-tertiary-fixed-dim drop-shadow-[0_0_6px_rgba(45,212,190,0.7)]">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
              {badge}
            </Link></div>
          );
        }

        return (
          <div key={item.href}>{groupHeading}<Link
            href={item.href}
            className="group flex items-center gap-3 rounded-xl border border-transparent px-4 py-3 text-sm text-surface-variant transition-colors hover:border-tertiary-fixed-dim/20 hover:bg-white/5 hover:text-surface-bright"
          >
            <span className="material-symbols-outlined text-primary-fixed-dim/90 transition-transform group-hover:scale-105 group-hover:text-tertiary-fixed-dim">{item.icon}</span>
            <span className="font-medium">{item.label}</span>
            {badge}
          </Link></div>
        );
      })}
    </div>
  );
}
