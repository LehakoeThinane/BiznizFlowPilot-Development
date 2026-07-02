"use client";

import { useEffect, useState } from "react";

import type { CurrentUser } from "@/types/api";
import { getCurrentUser, logout } from "@/lib/auth";

interface AuthGuardProps {
  children: React.ReactNode;
  onUserLoaded?: (user: CurrentUser) => void;
}

export function AuthGuard({ children, onUserLoaded }: AuthGuardProps) {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function verifySession() {
      try {
        // Relies on bfp_access httpOnly cookie — no localStorage check needed.
        const user = await getCurrentUser();
        if (!isMounted) return;
        onUserLoaded?.(user);
        setIsLoading(false);
      } catch {
        logout();
        if (!isMounted) return;
        window.location.replace("/login");
      }
    }

    void verifySession();
    return () => {
      isMounted = false;
    };
  }, [onUserLoaded]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0a0a0a]">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-xl font-bold text-white">
          B
        </div>
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-emerald-400" />
        <p className="text-xs text-[#555]">Verifying session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
