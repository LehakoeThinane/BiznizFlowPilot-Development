import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type RunStatusFilter = "all" | "pending" | "running" | "completed" | "failed";

function normalizeFilter(raw: string | null): RunStatusFilter {
  if (!raw) {
    return "all";
  }
  const normalized = raw.toLowerCase().trim();
  if (
    normalized === "all" ||
    normalized === "pending" ||
    normalized === "running" ||
    normalized === "completed" ||
    normalized === "failed"
  ) {
    return normalized;
  }
  return "all";
}

export async function GET(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  const cookie = request.headers.get("cookie");

  const statusFilter = normalizeFilter(request.nextUrl.searchParams.get("status"));

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/v1/workflows/runs`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
        ...(cookie ? { Cookie: cookie } : {}),
      },
      cache: "no-store",
    });

    const payload = (await response.json().catch(() => null)) as
      | { total: number; runs: Array<Record<string, unknown>>; detail?: string }
      | null;

    if (!response.ok || !payload) {
      return NextResponse.json(
        {
          detail:
            payload && typeof payload === "object" && "detail" in payload
              ? payload.detail
              : "Unable to load runs",
        },
        { status: response.status || 502 },
      );
    }

    const filteredRuns =
      statusFilter === "all"
        ? payload.runs
        : payload.runs.filter((run) => {
            const runStatus =
              typeof run.status === "string" ? run.status.toLowerCase() : "";
            if (statusFilter === "pending") {
              return runStatus === "queued" || runStatus === "pending";
            }
            return runStatus === statusFilter;
          });

    return NextResponse.json({
      total: filteredRuns.length,
      runs: filteredRuns,
    });
  } catch {
    return NextResponse.json({ detail: "Unable to load runs" }, { status: 502 });
  }
}
