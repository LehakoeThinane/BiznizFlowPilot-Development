import * as Sentry from "@sentry/nextjs";

// No-op unless NEXT_PUBLIC_SENTRY_DSN is set at build time, so local/dev
// runs need no Sentry account.
if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
