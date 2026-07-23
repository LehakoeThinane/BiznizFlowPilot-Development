import { NextRequest, NextResponse } from "next/server";

// BACKEND_URL (no NEXT_PUBLIC_ prefix) is the plain server-side runtime env
// var every other server-to-backend call in this container uses - matches
// docker-compose.prod.yml's "http://backend:8000" internal hop.
const BACKEND_BASE_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const authorization = request.headers.get("authorization");
  const cookie = request.headers.get("cookie");

  const { id } = await context.params;

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/v1/workflows/runs/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
        ...(cookie ? { Cookie: cookie } : {}),
      },
      cache: "no-store",
    });

    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | Record<string, unknown>
      | null;

    if (!response.ok || !payload) {
      return NextResponse.json(
        {
          detail:
            payload && typeof payload === "object" && "detail" in payload
              ? payload.detail
              : "Unable to load run details",
        },
        { status: response.status || 502 },
      );
    }

    return NextResponse.json(payload);
  } catch {
    return NextResponse.json(
      { detail: "Unable to load run details" },
      { status: 502 },
    );
  }
}
