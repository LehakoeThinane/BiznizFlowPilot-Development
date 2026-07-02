import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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
