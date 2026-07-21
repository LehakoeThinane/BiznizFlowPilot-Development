"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { ChatPanel } from "@/components/ChatPanel";
import { NotificationBell } from "@/components/NotificationBell";
import { RoleMenu } from "@/components/RoleMenu";
import { TrialBanner } from "@/components/TrialBanner";
import { UserContext } from "@/contexts/UserContext";
import { useDebounce } from "@/hooks/useDebounce";
import { logout } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import type { CurrentUser } from "@/types/api";

// ── Search types ────────────────────────────────────────────────────────────

interface SearchHit { id: string; label: string; sub: string; href: string }
interface SearchResults {
  customers: SearchHit[];
  products: SearchHit[];
  invoices: SearchHit[];
  tasks: SearchHit[];
}

function BizLogo() {
  return (
    <svg width="36" height="36" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10 8C10 5.79086 11.7909 4 14 4H22C27.5228 4 32 8.47715 32 14C32 16.9248 30.7441 19.5562 28.7412 21.3912C30.7441 23.2262 32 25.8576 32 28.8421C32 34.3649 27.5228 38.8421 22 38.8421H14C11.7909 38.8421 10 37.0512 10 34.8421V8Z" fill="#1E40AF"/>
      <path d="M22 4C27.5228 4 32 8.47715 32 14C32 16.9248 30.7441 19.5562 28.7412 21.3912L20 14H14V4H22Z" fill="#10B981"/>
    </svg>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [search, setSearch] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSearchDrop, setShowSearchDrop] = useState(false);

  const profileRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const debouncedSearch = useDebounce(search, 280);

  // Close profile dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setShowProfile(false);
      }
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearchDrop(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Global search
  useEffect(() => {
    const q = debouncedSearch.trim();
    if (q.length < 2) { setSearchResults(null); setShowSearchDrop(false); return; }
    setSearchLoading(true);
    apiRequest<{ results: SearchResults }>(`/api/v1/search?q=${encodeURIComponent(q)}`)
      .then((d) => { setSearchResults(d.results); setShowSearchDrop(true); })
      .catch(() => setSearchResults(null))
      .finally(() => setSearchLoading(false));
  }, [debouncedSearch]);

  function handleLogout() {
    logout();
    window.location.replace("/login");
  }

  const firstName = user?.full_name?.split(" ")[0] ?? user?.email ?? "";
  const initials = (user?.full_name ?? "?")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();

  const totalHits = searchResults
    ? Object.values(searchResults).reduce((s, arr) => s + arr.length, 0)
    : 0;

  const CATEGORY_LABELS: Record<keyof SearchResults, string> = {
    customers: "Customers",
    products: "Products",
    invoices: "Invoices",
    tasks: "Tasks",
  };

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <AuthGuard onUserLoaded={setUser}>
        <div className="flex h-screen overflow-hidden bg-transparent">

          {/* ── Mobile sidebar overlay ──────────────────────────────────── */}
          {sidebarOpen && (
            <div
              className="fixed inset-0 z-30 bg-black/50 md:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* ── Sidebar ─────────────────────────────────────────────────── */}
          <aside
            className={`
              sidebar fixed inset-y-0 left-0 z-40 flex w-72 shrink-0 flex-col justify-between
              overflow-y-auto transition-transform duration-200
              md:relative md:translate-x-0
              ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
            `}
          >
            {/* Top: branding + nav */}
            <div className="flex flex-col">
              <div className="flex items-center justify-between border-b border-white/10 px-6 py-7">
                <div>
                  <div className="glow-badge mb-4 flex h-11 w-11 items-center justify-center p-1.5">
                    <BizLogo />
                  </div>
                  <h2 className="text-lg font-bold leading-none tracking-tight text-surface-bright">
                    BiznizFlowPilot
                  </h2>
                  <p className="mt-1 text-[11px] text-primary-fixed-dim">ERP Control Center</p>
                </div>
                {/* Close button — mobile only */}
                <button
                  type="button"
                  onClick={() => setSidebarOpen(false)}
                  className="md:hidden rounded-lg p-1 text-surface-variant hover:bg-white/10"
                  aria-label="Close sidebar"
                >
                  <span className="material-symbols-outlined text-[20px]">close</span>
                </button>
              </div>

              <nav onClick={() => setSidebarOpen(false)} className="px-3 py-4">
                <RoleMenu role={user?.role ?? "staff"} />
              </nav>
            </div>

            {/* Bottom: support / settings / sign out */}
            <div className="border-t border-white/8 pb-4 pt-2">
              <a
                href="mailto:support@biznizflowpilot.com"
                className="flex items-center gap-3 px-4 py-3 text-sm text-surface-variant transition-colors hover:bg-white/5"
              >
                <span className="material-symbols-outlined text-primary-fixed-dim">help</span>
                <span>Support</span>
              </a>
              <Link
                href="/settings"
                onClick={() => setSidebarOpen(false)}
                className="flex items-center gap-3 px-4 py-3 text-sm text-surface-variant transition-colors hover:bg-white/5"
              >
                <span className="material-symbols-outlined text-primary-fixed-dim">settings</span>
                <span>Settings</span>
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-3 px-4 py-3 text-sm text-surface-variant transition-colors hover:bg-white/5"
              >
                <span className="material-symbols-outlined ms-16 text-primary-fixed-dim">logout</span>
                <span>Sign out</span>
              </button>
            </div>
          </aside>

          {/* ── Main content ─────────────────────────────────────────────── */}
          <div className="flex flex-1 flex-col overflow-hidden">
            <header className="flex h-14 shrink-0 items-center justify-between border-b border-outline-variant/80 bg-[#0d1628]/90 px-4 backdrop-blur md:px-6">

              {/* Left: hamburger (mobile) + search */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setSidebarOpen(true)}
                  className="md:hidden flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-high"
                  aria-label="Open sidebar"
                >
                  <span className="material-symbols-outlined">menu</span>
                </button>

                {/* Search bar */}
                <div ref={searchRef} className="relative">
                  <div className="flex w-64 items-center gap-2 rounded-xl border border-outline-variant bg-[#0a1528]/80 px-3 py-1.5 sm:w-96">
                    <span className="material-symbols-outlined ms-16 text-on-surface-variant">
                      {searchLoading ? "hourglass_empty" : "search"}
                    </span>
                    <input
                      type="text"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      onFocus={() => { if (searchResults && totalHits > 0) setShowSearchDrop(true); }}
                      placeholder="Search operations, files, or tasks..."
                      className="flex-1 bg-transparent text-xs text-white placeholder:text-on-surface-variant outline-none"
                    />
                    {search && (
                      <button
                        type="button"
                        onClick={() => { setSearch(""); setSearchResults(null); setShowSearchDrop(false); }}
                        className="text-on-surface-variant hover:text-white"
                        aria-label="Clear search"
                      >
                        <span className="material-symbols-outlined text-[16px]">close</span>
                      </button>
                    )}
                  </div>

                  {/* Search results dropdown */}
                  {showSearchDrop && searchResults && totalHits > 0 && (
                    <div className="absolute left-0 top-full z-50 mt-1 w-96 overflow-hidden rounded-xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
                      {(Object.entries(searchResults) as [keyof SearchResults, SearchHit[]][])
                        .filter(([, hits]) => hits.length > 0)
                        .map(([cat, hits]) => (
                          <div key={cat}>
                            <p className="px-3 pt-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                              {CATEGORY_LABELS[cat]}
                            </p>
                            {hits.map((hit) => (
                              <Link
                                key={hit.id}
                                href={hit.href}
                                onClick={() => { setSearch(""); setShowSearchDrop(false); }}
                                className="flex flex-col px-3 py-2 hover:bg-surface-container-high transition-colors"
                              >
                                <span className="text-sm text-white truncate">{hit.label}</span>
                                {hit.sub && (
                                  <span className="text-xs text-on-surface-variant truncate">{hit.sub}</span>
                                )}
                              </Link>
                            ))}
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {showSearchDrop && debouncedSearch.trim().length >= 2 && totalHits === 0 && !searchLoading && (
                    <div className="absolute left-0 top-full z-50 mt-1 w-96 rounded-xl border border-outline-variant bg-[#0f1c33] px-4 py-3 shadow-2xl">
                      <p className="text-sm text-on-surface-variant">No results for "{debouncedSearch}"</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Right actions */}
              <div className="flex items-center gap-3">
                <NotificationBell />
                <div className="h-6 w-px bg-outline-variant" />
                <div ref={profileRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setShowProfile((v) => !v)}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-surface-container-high"
                  >
                    <span className="hidden text-sm font-semibold text-primary-fixed-dim sm:block">
                      {firstName}
                    </span>
                    {user?.avatar_url ? (
                      <img src={user.avatar_url} alt="avatar" className="h-8 w-8 shrink-0 rounded-full object-cover" />
                    ) : (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-container text-xs font-bold text-on-primary-container">
                        {initials || "?"}
                      </div>
                    )}
                  </button>

                  {showProfile && (
                    <div className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border border-outline-variant bg-[#0f1c33] shadow-xl">
                      <div className="border-b border-outline-variant px-4 py-3">
                        <p className="text-sm font-semibold text-white">{user?.full_name ?? "—"}</p>
                        <p className="truncate text-xs text-on-surface-variant">{user?.email ?? ""}</p>
                        <span className="mt-1.5 inline-block rounded-full bg-primary-container px-2 py-0.5 text-[10px] font-medium capitalize text-on-primary-container">
                          {user?.role ?? ""}
                        </span>
                      </div>
                      <div className="py-1">
                        <Link
                          href="/settings"
                          onClick={() => setShowProfile(false)}
                          className="flex items-center gap-3 px-4 py-2.5 text-sm text-on-surface-variant transition-colors hover:bg-white/5"
                        >
                          <span className="material-symbols-outlined text-[18px]">settings</span>
                          Settings
                        </Link>
                        <button
                          type="button"
                          onClick={() => { setShowProfile(false); handleLogout(); }}
                          className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-rose-400 transition-colors hover:bg-white/5"
                        >
                          <span className="material-symbols-outlined text-[18px]">logout</span>
                          Sign out
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </header>

            <TrialBanner />

            <main className="flex-1 overflow-y-auto p-4 md:p-6">
              {children}
            </main>
          </div>
        </div>

        <ChatPanel />
      </AuthGuard>
    </UserContext.Provider>
  );
}
