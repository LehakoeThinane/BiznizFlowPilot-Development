"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type OsId = "windows" | "mac" | "linux";

interface DownloadOption {
  id: OsId;
  label: string;
  icon: string;
  file: string;
  version: string;
  size: string;
  href: string | null;
}

// Update href/version/size once a platform's installer is built and hosted
// (see desktop/README.md - electron-builder's dist/ output, copied into the
// VM's downloads/ folder, served at /downloads/<file> off this same domain).
const DOWNLOADS: DownloadOption[] = [
  { id: "windows", label: "Windows", icon: "desktop_windows", file: "BiznizFlowPilot-Setup.exe", version: "0.1.0", size: "78 MB", href: "/downloads/BiznizFlowPilot-Setup.exe" },
  { id: "mac", label: "macOS", icon: "laptop_mac", file: "BiznizFlowPilot.dmg", version: "0.1.0", size: "94 MB", href: null },
  { id: "linux", label: "Linux", icon: "terminal", file: "BiznizFlowPilot.AppImage", version: "0.1.0", size: "98 MB", href: null },
];

function detectOs(): OsId | null {
  if (typeof navigator === "undefined") return null;
  const platform = `${navigator.userAgent} ${navigator.platform ?? ""}`.toLowerCase();
  if (platform.includes("mac")) return "mac";
  if (platform.includes("win")) return "windows";
  if (platform.includes("linux") || platform.includes("x11")) return "linux";
  return null;
}

export default function DownloadPage() {
  const [detected, setDetected] = useState<OsId | null>(null);

  useEffect(() => {
    setDetected(detectOs());
  }, []);

  return (
    <main className="min-h-screen px-4 pb-24 pt-20 sm:px-8">
      <div className="mx-auto max-w-5xl text-center">
        <p className="text-label-caps text-brand">Download</p>
        <h1 className="text-display mt-3 text-balance">Get BiznizFlowPilot on your desktop</h1>
        <p className="text-body-base mx-auto mt-4 max-w-md text-muted">
          Already have an invite from your company? Install the app, sign in with your invite
          link, and you&apos;re in.
        </p>

        <div className="mt-14 grid gap-5 sm:grid-cols-3">
          {DOWNLOADS.map((option) => {
            const isRecommended = detected === option.id && option.href !== null;
            const isAvailable = option.href !== null;
            return (
              <a
                key={option.id}
                href={option.href ?? undefined}
                aria-disabled={!isAvailable}
                onClick={(event) => {
                  if (!isAvailable) event.preventDefault();
                }}
                className={`group relative flex flex-col items-center rounded-2xl border p-8 text-center transition-colors ${
                  isRecommended
                    ? "border-tertiary-fixed-dim/50 bg-surface shadow-[0_0_0_1px_rgba(45,212,191,0.12),0_20px_60px_rgba(2,8,20,0.45)]"
                    : isAvailable
                      ? "border-border bg-surface-dim hover:border-brand/40"
                      : "border-border bg-surface-dim opacity-60"
                }`}
              >
                {isRecommended ? (
                  <span className="text-label-caps absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-tertiary-fixed-dim px-3 py-1 text-tertiary">
                    Recommended for your system
                  </span>
                ) : null}

                <span
                  className={`material-symbols-outlined flex h-14 w-14 items-center justify-center rounded-2xl text-[28px] ${
                    isRecommended ? "bg-tertiary-fixed-dim/15 text-tertiary-fixed-dim" : "bg-surface text-on-surface-variant"
                  }`}
                >
                  {option.icon}
                </span>

                <h2 className="text-h2 mt-4">{option.label}</h2>
                <p className="text-body-sm mt-1 text-on-surface-variant">
                  {isAvailable ? `${option.file} · v${option.version} · ${option.size}` : "Not yet available"}
                </p>

                <span
                  className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors ${
                    isRecommended
                      ? "erp-button-primary"
                      : isAvailable
                        ? "border border-border text-on-surface group-hover:bg-[#1f1f1f]"
                        : "border border-border text-on-surface-variant"
                  }`}
                >
                  {isAvailable ? `Download for ${option.label}` : "Coming soon"}
                </span>

                {option.id === "windows" && isAvailable ? (
                  <p className="text-body-sm mt-4 text-on-surface-variant">
                    Unsigned build for now - Windows SmartScreen will warn on install. Click
                    &quot;More info&quot; → &quot;Run anyway&quot; to proceed.
                  </p>
                ) : null}
              </a>
            );
          })}
        </div>

        <p className="text-body-sm mt-14 text-muted">
          Don&apos;t have an invite yet?{" "}
          <Link href="/pricing" className="font-medium text-brand hover:underline">
            View pricing
          </Link>
        </p>
      </div>
    </main>
  );
}
