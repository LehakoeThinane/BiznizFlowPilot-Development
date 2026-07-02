import { ApiError } from "@/lib/api";

type QueryValue = string | number | boolean | null | undefined;

interface PlatformApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  query?: Record<string, QueryValue>;
  _skipRefresh?: boolean;
}

// Same relative-URL/proxy convention as lib/api.ts.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const REQUEST_TIMEOUT_MS = 15_000;
const PLATFORM_SESSION_TOKEN_KEY = "bfp_platform_at";

// Deliberately a separate sessionStorage key and separate refresh endpoint
// from lib/api.ts's tenant token - platform and tenant sessions must never
// be able to authenticate each other's requests.
export function getPlatformAccessToken(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    return sessionStorage.getItem(PLATFORM_SESSION_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setPlatformAccessToken(token: string): void {
  try {
    sessionStorage.setItem(PLATFORM_SESSION_TOKEN_KEY, token);
  } catch {
    // sessionStorage unavailable (SSR or private browsing restriction)
  }
}

export function clearPlatformAccessToken(): void {
  try {
    sessionStorage.removeItem(PLATFORM_SESSION_TOKEN_KEY);
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
  }
  return "Request failed";
}

let _refreshPromise: Promise<string | null> | null = null;

async function tryPlatformRefresh(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const res = await fetch(toAbsoluteUrl("/platform/v1/auth/refresh"), {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "include",
      });

      if (!res.ok) {
        clearPlatformAccessToken();
        const onLoginPage = window.location.pathname === "/platform/login";
        if (!onLoginPage) window.location.replace("/platform/login");
        return null;
      }

      const data = (await res.json()) as { access_token: string };
      setPlatformAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

export async function platformApiRequest<T>(
  path: string,
  options: PlatformApiRequestOptions = {},
): Promise<T> {
  const { query, body, headers, _skipRefresh, ...requestInit } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");

  const token = getPlatformAccessToken();
  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  let requestBody: BodyInit | undefined;
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
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
      credentials: "include",
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Request timed out. Please try again.", 408);
    }
    throw err;
  }
  clearTimeout(timeoutId);

  if (response.status === 401 && !_skipRefresh) {
    const newToken = await tryPlatformRefresh();
    if (newToken) {
      return platformApiRequest<T>(path, { ...options, _skipRefresh: true });
    }
    throw new ApiError("Session expired. Please log in again.", 401);
  }

  if (response.status === 204) return undefined as T;

  const payload = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload), response.status);
  }
  return payload as T;
}
