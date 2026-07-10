import { captureRequestError } from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  } else if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
}

// Safe to export unconditionally - a no-op when Sentry.init was never
// called (SENTRY_DSN unset), same as every other Sentry SDK call.
export const onRequestError = captureRequestError;
