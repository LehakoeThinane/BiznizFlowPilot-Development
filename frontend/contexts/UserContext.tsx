"use client";

import { createContext, useContext } from "react";
import type { CurrentUser } from "@/types/api";

interface UserContextValue {
  user: CurrentUser | null;
  setUser: (user: CurrentUser | null) => void;
}

export const UserContext = createContext<UserContextValue>({
  user: null,
  setUser: () => {},
});

export function useUser(): UserContextValue {
  return useContext(UserContext);
}
