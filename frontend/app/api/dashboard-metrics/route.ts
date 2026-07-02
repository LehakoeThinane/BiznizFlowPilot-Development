import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  const cookie = request.headers.get("cookie");

  try {
    const headers: HeadersInit = { Accept: "application/json" };
    if (authorization) headers.Authorization = authorization;
    if (cookie) headers.Cookie = cookie;

    const response = await fetch(`${BACKEND_BASE_URL}/api/v1/dashboard`, {
      method: "GET",
      headers,
      cache: "no-store",
    });

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401) {
        return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
      }
      return NextResponse.json(
        { detail: payload?.detail ?? "Failed to load dashboard" },
        { status: response.status >= 400 && response.status < 500 ? response.status : 502 },
      );
    }

    // Shape into the DashboardMetricsResponse the page expects
    const d = payload as BackendDashboard;
    return NextResponse.json({
      sales: d.sales,
      leads: d.leads,
      tasks: d.tasks,
      inventory: d.inventory,
      workflows: d.workflows,
      refreshedAt: d.refreshed_at,
    });
  } catch {
    return NextResponse.json(
      { detail: "Unable to load dashboard metrics" },
      { status: 502 },
    );
  }
}

interface BackendDashboard {
  sales: {
    revenue_total: string;
    revenue_this_month: string;
    open_orders: number;
    orders_total: number;
  };
  leads: {
    open_leads: number;
    new_leads: number;
    qualified_leads: number;
    won_leads: number;
    lost_leads: number;
  };
  tasks: {
    overdue: number;
    due_today: number;
    pending: number;
  };
  inventory: {
    low_stock_products: number;
    out_of_stock_products: number;
    total_active_products: number;
    total_suppliers: number;
  };
  workflows: {
    total_definitions: number;
    active_runs: number;
    failed_runs_today: number;
  };
  refreshed_at: string;
}
