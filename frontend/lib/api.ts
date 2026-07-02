type QueryValue = string | number | boolean | null | undefined;

interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  authToken?: string | null;
  query?: Record<string, QueryValue>;
  /** Skip the automatic 401 → refresh retry (used internally to avoid infinite loops). */
  _skipRefresh?: boolean;
}

// Always use relative URLs so requests go through the Next.js proxy (same-origin).
// NEXT_PUBLIC_API_BASE_URL can override this for deployments where the API lives elsewhere.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

const REQUEST_TIMEOUT_MS = 15_000;
const SESSION_TOKEN_KEY = "bfp_at";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Access token stored in sessionStorage so it survives same-tab page navigations
// but is cleared when the tab closes. Falls back to the httpOnly cookie when absent.
export function getAccessToken(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    return sessionStorage.getItem(SESSION_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): void {
  try {
    sessionStorage.setItem(SESSION_TOKEN_KEY, token);
  } catch {
    // sessionStorage unavailable (SSR or private browsing restriction)
  }
}

export function clearAccessToken(): void {
  try {
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
  } catch {
    // ignore
  }
}

function toAbsoluteUrl(path: string, query?: Record<string, QueryValue>): string {
  const isAbsolute = /^https?:\/\//i.test(path);
  const base = isAbsolute ? path : `${API_BASE_URL}${path}`;
  const url = new URL(base, isAbsolute ? undefined : window.location.origin);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function extractErrorMessage(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const d = detail as { message?: unknown; errors?: unknown };
      if (typeof d.message === "string") {
        if (Array.isArray(d.errors) && d.errors.length > 0) {
          return `${d.message}: ${(d.errors as unknown[]).join("; ")}`;
        }
        return d.message;
      }
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => {
          if (!entry || typeof entry !== "object") return null;
          const item = entry as { loc?: unknown; msg?: unknown };
          const msg = typeof item.msg === "string" ? item.msg : null;
          if (!msg) return null;
          if (Array.isArray(item.loc)) {
            const path = item.loc
              .filter((s): s is string => typeof s === "string")
              .filter((s) => s !== "body");
            if (path.length > 0) return `${path.join(".")}: ${msg}`;
          }
          return msg;
        })
        .filter((m): m is string => Boolean(m));
      if (messages.length > 0) return messages.join("; ");
    }
  }
  return "Request failed";
}

// Deduplicate concurrent refresh calls so only one request fires at a time.
let _refreshPromise: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const { logout } = await import("@/lib/auth");

      // The httpOnly bfp_refresh cookie is sent automatically via credentials:include.
      const res = await fetch(toAbsoluteUrl("/api/v1/auth/refresh"), {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "include",
      });

      if (!res.ok) {
        logout();
        // Don't redirect if already on an auth page — prevents redirect loops.
        const onAuthPage = /^\/(login|register)(\/|$)/.test(window.location.pathname);
        if (!onAuthPage) window.location.replace("/login");
        return null;
      }

      const data = (await res.json()) as { access_token: string };
      setAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

export async function downloadFile(
  path: string,
  filename: string,
  query?: Record<string, QueryValue>,
): Promise<void> {
  const token = getAccessToken();
  const headers = new Headers({ Accept: "text/csv" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(toAbsoluteUrl(path, query), {
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Request timed out. Please try again.", 408);
    }
    throw err;
  }
  clearTimeout(timeoutId);

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(extractErrorMessage(payload), response.status);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { authToken, query, body, headers, _skipRefresh, ...requestInit } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");

  // Only real JWTs (start with "eyJ") go in the Authorization header.
  // getStoredToken() returns "1" (session indicator) — treat that as absent
  // and fall back to the real JWT stored in sessionStorage.
  const providedJwt = authToken && authToken.startsWith("eyJ") ? authToken : null;
  const effectiveToken = providedJwt ?? getAccessToken();
  if (effectiveToken) {
    requestHeaders.set("Authorization", `Bearer ${effectiveToken}`);
  }

  let requestBody: BodyInit | undefined;
  if (body !== undefined) {
    if (body instanceof FormData) {
      requestBody = body;
    } else {
      requestHeaders.set("Content-Type", "application/json");
      requestBody = JSON.stringify(body);
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(toAbsoluteUrl(path, query), {
      ...requestInit,
      headers: requestHeaders,
      body: requestBody,
      signal: controller.signal,
      credentials: "include", // also send httpOnly cookies on every request
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Request timed out. Please try again.", 408);
    }
    throw err;
  }
  clearTimeout(timeoutId);

  // Attempt a silent token refresh on 401, then retry once
  if (response.status === 401 && !_skipRefresh) {
    const newToken = await tryRefresh();
    if (newToken) {
      return apiRequest<T>(path, { ...options, authToken: newToken, _skipRefresh: true });
    }
    // tryRefresh already called logout() and redirect if refresh failed
    throw new ApiError("Session expired. Please log in again.", 401);
  }

  if (response.status === 204) return undefined as T;

  const payload = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload), response.status);
  }
  return payload as T;
}
