import * as Sentry from "@sentry/nextjs";

// No-op unless SENTRY_DSN is set, so local/dev runs need no Sentry account.
if (process.env.SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
