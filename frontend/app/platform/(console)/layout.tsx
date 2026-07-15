"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { PlatformAuthGuard } from "@/components/PlatformAuthGuard";
import { platformLogout } from "@/lib/platform-auth";
import type { CurrentPlatformAdmin } from "@/types/api";

const NAV = [
  { label: "Overview", href: "/platform" },
  { label: "Organizations", href: "/platform/organizations" },
  { label: "Settings", href: "/platform/settings" },
];

export default function PlatformConsoleLayout({ children }: { children: React.ReactNode }) {
  const [admin, setAdmin] = useState<CurrentPlatformAdmin | null>(null);
  const pathname = usePathname();

  function handleLogout() {
    platformLogout();
    window.location.replace("/platform/login");
  }

  return (
    <PlatformAuthGuard onAdminLoaded={setAdmin}>
      <div className="min-h-screen bg-[#0a0a12]">
        <header className="flex h-14 items-center justify-between border-b border-[#22222e] bg-[#12121a] px-6">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-sm font-bold text-white">
                P
              </div>
              <span className="text-sm font-semibold text-white">Platform Console</span>
            </div>
            <nav className="flex items-center gap-1">
              {NAV.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                      active
                        ? "bg-violet-600/20 text-violet-300"
                        : "text-[#999] hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            {admin && (
              <div className="text-right">
                <p className="text-xs font-medium text-white">{admin.full_name}</p>
                <p className="text-[10px] uppercase tracking-wide text-[#777]">
                  {admin.platform_role.replace("_", " ")}
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-[#2a2a3a] px-3 py-1.5 text-xs text-[#aaa] hover:bg-white/5 hover:text-white"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </div>
    </PlatformAuthGuard>
  );
}
