"use client";

import { useEffect, useState } from "react";

import type { CurrentUser } from "@/types/api";
import { getCurrentUser, logout } from "@/lib/auth";
import { AppLoadingScreen } from "@/components/AppLoadingScreen";

interface AuthGuardProps {
  children: React.ReactNode;
  onUserLoaded?: (user: CurrentUser) => void;
}

// Local/staging session checks can resolve in well under one animation
// cycle, so the loading screen would otherwise flash and disappear before
// its logo animation is even visible - hold it up for at least this long.
const MIN_VISIBLE_MS = 900;

export function AuthGuard({ children, onUserLoaded }: AuthGuardProps) {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const startedAt = Date.now();

    function finishLoading() {
      const elapsed = Date.now() - startedAt;
      const remaining = MIN_VISIBLE_MS - elapsed;
      if (remaining <= 0) {
        setIsLoading(false);
      } else {
        setTimeout(() => {
          if (isMounted) setIsLoading(false);
        }, remaining);
      }
    }

    async function verifySession() {
      try {
        // Relies on bfp_access httpOnly cookie — no localStorage check needed.
        const user = await getCurrentUser();
        if (!isMounted) return;
        onUserLoaded?.(user);
        finishLoading();
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
    return <AppLoadingScreen label="Verifying session…" />;
  }

  return <>{children}</>;
}
