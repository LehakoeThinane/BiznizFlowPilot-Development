import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: currentDir,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: "/platform/v1/:path*",
        destination: `${BACKEND_URL}/platform/v1/:path*`,
      },
    ];
  },
};

// withSentryConfig is a safe no-op wrapper when there's no Sentry org/project
// configured (SENTRY_ORG/SENTRY_PROJECT unset) - it just skips the source-map
// upload step, so this needs no Sentry account to build locally.
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  silent: true,
  disableLogger: true,
});
