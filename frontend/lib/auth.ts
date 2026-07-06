import { apiRequest, clearAccessToken, setAccessToken } from "@/lib/api";
import type {
  CurrentUser,
  LoginRequest,
  TokenResponse,
} from "@/types/api";

// bfp_session=1 is a non-httpOnly cookie the backend sets alongside the httpOnly
// bfp_access cookie. JS reads this to know whether the user is authenticated
// without touching the real JWT.
export function getStoredToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)bfp_session=([^;]+)/);
  return match ? match[1] : null;
}

export function setStoredTokens(accessToken: string): void {
  setAccessToken(accessToken);
}

export function logout(): void {
  if (typeof window === "undefined") return;
  clearAccessToken();
  document.cookie = "bfp_session=; Max-Age=0; Path=/";
  void fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => null);
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const tokens = await apiRequest<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: payload,
    _skipRefresh: true,
  });
  setAccessToken(tokens.access_token);
  return tokens;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/api/v1/users/me", { method: "GET", _skipRefresh: true });
}

export async function acceptInvite(payload: {
  token: string;
  password: string;
  first_name: string;
  last_name: string;
}): Promise<TokenResponse> {
  const tokens = await apiRequest<TokenResponse>("/api/v1/auth/invite/accept", {
    method: "POST",
    body: payload,
    _skipRefresh: true,
  });
  setAccessToken(tokens.access_token);
  return tokens;
}
