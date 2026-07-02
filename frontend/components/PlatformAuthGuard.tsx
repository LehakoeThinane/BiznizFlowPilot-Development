"use client";

import { useEffect, useState } from "react";

import type { CurrentPlatformAdmin } from "@/types/api";
import { getCurrentPlatformAdmin, platformLogout } from "@/lib/platform-auth";

interface PlatformAuthGuardProps {
  children: React.ReactNode;
  onAdminLoaded?: (admin: CurrentPlatformAdmin) => void;
}

export function PlatformAuthGuard({ children, onAdminLoaded }: PlatformAuthGuardProps) {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function verifySession() {
      try {
        const admin = await getCurrentPlatformAdmin();
        if (!isMounted) return;
        onAdminLoaded?.(admin);
        setIsLoading(false);
      } catch {
        platformLogout();
        if (!isMounted) return;
        window.location.replace("/platform/login");
      }
    }

    void verifySession();
    return () => {
      isMounted = false;
    };
  }, [onAdminLoaded]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0a0a12]">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-600 text-xl font-bold text-white">
          P
        </div>
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-violet-400" />
        <p className="text-xs text-[#555]">Verifying platform session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
