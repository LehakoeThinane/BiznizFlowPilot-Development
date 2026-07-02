"use client";

import { useContext, useEffect } from "react";
import { useRouter } from "next/navigation";

import { UserContext } from "@/contexts/UserContext";
import type { UserRole } from "@/types/api";

/**
 * Page-level role guard. AuthGuard only checks session validity (any
 * authenticated user can otherwise navigate directly to any dashboard
 * URL) - pages exposing cross-subsidiary data or invite issuance need
 * this on top of AuthGuard, not instead of it.
 */
export function useRequireRole(allowed: UserRole[]): { allowed: boolean; checked: boolean } {
  const { user } = useContext(UserContext);
  const router = useRouter();

  const checked = user !== null;
  const isAllowed = checked && allowed.includes(user.role);

  useEffect(() => {
    if (checked && !isAllowed) {
      router.replace("/home");
    }
  }, [checked, isAllowed, router]);

  return { allowed: isAllowed, checked };
}
