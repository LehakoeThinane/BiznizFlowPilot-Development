import { clearPlatformAccessToken, platformApiRequest, setPlatformAccessToken } from "@/lib/platform-api";
import type { CurrentPlatformAdmin, PlatformLoginRequest, PlatformTokenResponse } from "@/types/api";

export function platformLogout(): void {
  if (typeof window === "undefined") return;
  clearPlatformAccessToken();
  void fetch("/platform/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => null);
}

export async function platformLogin(payload: PlatformLoginRequest): Promise<PlatformTokenResponse> {
  const tokens = await platformApiRequest<PlatformTokenResponse>("/platform/v1/auth/login", {
    method: "POST",
    body: payload,
    _skipRefresh: true,
  });
  setPlatformAccessToken(tokens.access_token);
  return tokens;
}

export async function getCurrentPlatformAdmin(): Promise<CurrentPlatformAdmin> {
  return platformApiRequest<CurrentPlatformAdmin>("/platform/v1/admins/me", {
    method: "GET",
    _skipRefresh: true,
  });
}
