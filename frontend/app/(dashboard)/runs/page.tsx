"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { logout } from "@/lib/auth";
import { Pagination } from "@/components/Pagination";
import type {
  Workflow,
  WorkflowListResponse,
  WorkflowRun,
  WorkflowRunListResponse,
} from "@/types/api";

type RunFilter = "all" | "pending" | "running" | "completed" | "failed";
type RunSortDirection = "desc" | "asc";
type WorkflowOption = { id: string; name: string };

const REFRESH_SECONDS = 10;
const PAGE_SIZE = 20;

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function statusLabel(status: WorkflowRun["status"]): string {
  if (status === "queued") {
    return "Pending";
  }
  return status.slice(0, 1).toUpperCase() + status.slice(1);
}

function statusClass(status: WorkflowRun["status"]): string {
  if (status === "queued") {
    return "bg-amber-500/20 text-amber-300";
  }
  if (status === "running") {
    return "bg-blue-500/20 text-blue-300";
  }
  if (status === "completed") {
    return "bg-emerald-500/20 text-emerald-300";
  }
  return "bg-rose-500/20 text-rose-300";
}

function startedAt(run: WorkflowRun): string {
  return run.started_at ?? run.created_at;
}

function completedAt(run: WorkflowRun): string | null {
  if (run.status === "completed" || run.status === "failed") {
    return run.finished_at ?? run.updated_at;
  }
  return null;
}

function durationText(run: WorkflowRun): string {
  const start = startedAt(run);
  const done = completedAt(run);
  if (!done) {
    return "-";
  }

  const startTime = new Date(start).getTime();
  const doneTime = new Date(done).getTime();
  if (Number.isNaN(startTime) || Number.isNaN(doneTime) || doneTime < startTime) {
    return "-";
  }

  const totalSeconds = Math.floor((doneTime - startTime) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

function formatErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "string") {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (error && typeof error === "object" && "message" in error) {
    const candidate = (error as { message?: unknown }).message;
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
    }
  }
  return fallback;
}

function isWorkflowRunPayload(value: unknown): value is WorkflowRun {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string" && typeof candidate.status === "string";
}

function csvValue(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replaceAll('"', '""')}"`;
  }
  return value;
}

function downloadCsv(filename: string, rows: string[][]): void {
  const csvBody = rows.map((row) => row.map(csvValue).join(",")).join("\n");
  const blob = new Blob([csvBody], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export default function WorkflowRunsPage() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [workflowNameMap, setWorkflowNameMap] = useState<Record<string, string>>({});
  const [workflowOptions, setWorkflowOptions] = useState<WorkflowOption[]>([]);
  const [filter, setFilter] = useState<RunFilter>("all");
  const [workflowFilter, setWorkflowFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortDirection, setSortDirection] = useState<RunSortDirection>("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(REFRESH_SECONDS);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [page, setPage] = useState(1);

  const loadRuns = useCallback(
    async (mode: "initial" | "refresh" | "manual" = "initial") => {
      if (mode === "initial") {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);

      try {
        const [runsPayload, workflowsResponse] = await Promise.all([
          apiRequest<WorkflowRunListResponse>("/api/v1/runs", {
            method: "GET",
          }),
          apiRequest<WorkflowListResponse>("/api/v1/workflows", {
            method: "GET",
          }),
        ]);

        const map: Record<string, string> = {};
        const options: WorkflowOption[] = [];
        for (const workflow of workflowsResponse.workflows as Workflow[]) {
          map[workflow.id] = workflow.name;
          options.push({ id: workflow.id, name: workflow.name });
        }
        options.sort((left, right) => left.name.localeCompare(right.name));

        setRuns(runsPayload.runs);
        setWorkflowNameMap(map);
        setWorkflowOptions(options);
        setSecondsUntilRefresh(REFRESH_SECONDS);
      } catch (requestError) {
        if (requestError instanceof ApiError && requestError.status === 401) {
          logout();
          window.location.replace("/login");
          return;
        }
        setError(formatErrorMessage(requestError, "Unable to load workflow runs"));
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [],
  );

  const loadRunDetails = useCallback(async (run: WorkflowRun) => {
    setSelectedRun(run);
    setIsDetailsLoading(true);
    try {
      const payload = await apiRequest<WorkflowRun>(`/api/v1/runs/${run.id}`, {
        method: "GET",
      });
      if (!isWorkflowRunPayload(payload)) {
        throw new Error("Unable to load run details");
      }
      setSelectedRun(payload);
    } catch (detailError) {
      setError(formatErrorMessage(detailError, "Unable to load run details"));
    } finally {
      setIsDetailsLoading(false);
    }
  }, []);

  const filteredRuns = useMemo(() => {
    let nextRuns = [...runs];

    if (filter !== "all") {
      nextRuns = nextRuns.filter((run) => {
        if (filter === "pending") {
          return run.status === "queued";
        }
        return run.status === filter;
      });
    }

    if (workflowFilter !== "all") {
      nextRuns = nextRuns.filter((run) => run.workflow_id === workflowFilter);
    }

    const startTimestamp = startDate
      ? new Date(`${startDate}T00:00:00`).getTime()
      : null;
    const endTimestamp = endDate
      ? new Date(`${endDate}T23:59:59.999`).getTime()
      : null;

    if (startTimestamp !== null || endTimestamp !== null) {
      nextRuns = nextRuns.filter((run) => {
        const runTimestamp = new Date(startedAt(run)).getTime();
        if (Number.isNaN(runTimestamp)) {
          return false;
        }
        if (startTimestamp !== null && runTimestamp < startTimestamp) {
          return false;
        }
        if (endTimestamp !== null && runTimestamp > endTimestamp) {
          return false;
        }
        return true;
      });
    }

    nextRuns.sort((left, right) => {
      const leftTime = new Date(startedAt(left)).getTime();
      const rightTime = new Date(startedAt(right)).getTime();
      const safeLeft = Number.isNaN(leftTime) ? 0 : leftTime;
      const safeRight = Number.isNaN(rightTime) ? 0 : rightTime;
      return safeLeft - safeRight;
    });

    if (sortDirection === "desc") {
      nextRuns.reverse();
    }

    return nextRuns;
  }, [endDate, filter, runs, sortDirection, startDate, workflowFilter]);

  const pagedRuns = useMemo(
    () => filteredRuns.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filteredRuns, page],
  );

  const hasActiveRuns = useMemo(
    () => filteredRuns.some((run) => run.status === "queued" || run.status === "running"),
    [filteredRuns],
  );

  const shouldAutoRefresh = hasActiveRuns || filter === "running" || filter === "pending";

  const exportRunsCsv = useCallback(() => {
    if (filteredRuns.length === 0) {
      return;
    }

    const rows: string[][] = [
      ["Run ID", "Workflow", "Status", "Started", "Completed", "Duration", "Event ID", "Error"],
    ];

    for (const run of filteredRuns) {
      const workflowName = run.workflow_id
        ? (workflowNameMap[run.workflow_id] ?? run.workflow_id)
        : "Unknown workflow";
      rows.push([
        run.id,
        workflowName,
        statusLabel(run.status),
        formatDate(startedAt(run)),
        formatDate(completedAt(run)),
        durationText(run),
        run.event_id ?? "",
        run.error_message ?? "",
      ]);
    }

    const datePart = new Date().toISOString().slice(0, 10);
    downloadCsv(`workflow-runs-${datePart}.csv`, rows);
  }, [filteredRuns, workflowNameMap]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRuns("initial");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns]);

  useEffect(() => { setPage(1); }, [filter, workflowFilter, startDate, endDate, sortDirection]);

  useEffect(() => {
    if (!shouldAutoRefresh) {
      return;
    }

    const interval = window.setInterval(() => {
      setSecondsUntilRefresh((previous) => {
        if (previous <= 1) {
          void loadRuns("refresh");
          return REFRESH_SECONDS;
        }
        return previous - 1;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [loadRuns, shouldAutoRefresh]);

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Workflow Runs</h1>
          <p className="mt-1 text-sm text-muted">
            Execution history for all workflow runs.
          </p>
          <p className="mt-1 text-xs text-muted">
            {shouldAutoRefresh
              ? `Auto-refresh in ${secondsUntilRefresh}s`
              : "Auto-refresh paused (no active runs)"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            id="status-filter"
            aria-label="Filter by status"
            className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm"
            value={filter}
            onChange={(event) => setFilter(event.target.value as RunFilter)}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <select
            aria-label="Filter by workflow"
            className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm"
            value={workflowFilter}
            onChange={(event) => setWorkflowFilter(event.target.value)}
          >
            <option value="all">All workflows</option>
            {workflowOptions.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm"
            aria-label="Start date"
          />
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm"
            aria-label="End date"
          />
          <button
            type="button"
            onClick={() =>
              setSortDirection((previous) => (previous === "desc" ? "asc" : "desc"))
            }
            className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5"
          >
            {sortDirection === "desc" ? "Newest First" : "Oldest First"}
          </button>
          <button
            type="button"
            onClick={() => {
              setFilter("all");
              setWorkflowFilter("all");
              setStartDate("");
              setEndDate("");
              setSortDirection("desc");
            }}
            className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={exportRunsCsv}
            disabled={filteredRuns.length === 0}
            className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5 disabled:opacity-50"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => void loadRuns("manual")}
            className="rounded-md border border-border px-3 py-2 text-sm text-[#aaa] hover:bg-white/5"
            disabled={isRefreshing}
          >
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      <p className="text-sm text-muted">
        Showing {filteredRuns.length} of {runs.length} run{runs.length === 1 ? "" : "s"}.
        {filteredRuns.length !== runs.length && ` (${filteredRuns.length} filtered)`}
      </p>

      {error ? (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{formatErrorMessage(error, "Unable to load workflow runs")}</p>
          <button
            type="button"
            className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium hover:bg-red-900/20"
            onClick={() => void loadRuns("manual")}
          >
            Retry
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">
          Loading workflow runs...
        </div>
      ) : filteredRuns.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">
          No workflow runs found for the current filters.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="min-w-full text-sm">
            <thead className="bg-[#1a1a1a] text-left">
              <tr>
                <th className="px-4 py-3 font-medium text-[#aaa]">Workflow</th>
                <th className="px-4 py-3 font-medium text-[#aaa]">Status</th>
                <th className="px-4 py-3 font-medium text-[#aaa]">Started</th>
                <th className="px-4 py-3 font-medium text-[#aaa]">Completed</th>
                <th className="px-4 py-3 font-medium text-[#aaa]">Duration</th>
              </tr>
            </thead>
            <tbody>
              {pagedRuns.map((run) => (
                <tr
                  key={run.id}
                  className="cursor-pointer border-t border-border hover:bg-white/2"
                  onClick={() => void loadRunDetails(run)}
                >
                  <td className="px-4 py-3 text-white">
                    {run.workflow_id
                      ? (workflowNameMap[run.workflow_id] ?? `Workflow ${run.workflow_id.slice(0, 8)}`)
                      : "Unknown workflow"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={[
                        "inline-flex rounded-full px-2 py-1 text-xs font-semibold",
                        statusClass(run.status),
                      ].join(" ")}
                    >
                      {statusLabel(run.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#aaa]">{formatDate(startedAt(run))}</td>
                  <td className="px-4 py-3 text-[#aaa]">{formatDate(completedAt(run))}</td>
                  <td className="px-4 py-3 text-[#aaa]">{durationText(run)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={page}
            totalPages={Math.max(1, Math.ceil(filteredRuns.length / PAGE_SIZE))}
            totalItems={filteredRuns.length}
            pageSize={PAGE_SIZE}
            onPrev={() => setPage((p) => p - 1)}
            onNext={() => setPage((p) => p + 1)}
          />
        </div>
      )}

      {selectedRun ? (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => setSelectedRun(null)}
            aria-label="Close run details"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-[#141414] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Run Details</h2>
              <button
                type="button"
                onClick={() => setSelectedRun(null)}
                className="rounded-md border border-border px-3 py-1 text-sm text-[#aaa] hover:bg-white/5"
              >
                Close
              </button>
            </div>

            {isDetailsLoading ? (
              <p className="text-sm text-muted">Loading details...</p>
            ) : (
              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Run ID</p>
                    <p className="mt-1 break-all text-[#ccc]">{selectedRun.id}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Status</p>
                    <p className="mt-1 text-[#ccc]">{statusLabel(selectedRun.status)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Workflow</p>
                    <p className="mt-1 break-all text-[#ccc]">
                      {selectedRun.workflow_id
                        ? (workflowNameMap[selectedRun.workflow_id] ?? selectedRun.workflow_id)
                        : "-"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Event ID</p>
                    <p className="mt-1 break-all text-[#ccc]">{selectedRun.event_id ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Started</p>
                    <p className="mt-1 text-[#ccc]">{formatDate(startedAt(selectedRun))}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Completed</p>
                    <p className="mt-1 text-[#ccc]">{formatDate(completedAt(selectedRun))}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Execution Logs</p>
                  <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-slate-900 p-3 text-xs text-slate-100">
                    <code>
                      {Array.isArray((selectedRun.results as { logs?: unknown }).logs)
                        ? JSON.stringify(
                            (selectedRun.results as { logs: unknown[] }).logs,
                            null,
                            2,
                          )
                        : "No execution logs available."}
                    </code>
                  </pre>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Result Data</p>
                  <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-slate-900 p-3 text-xs text-slate-100">
                    <code>{JSON.stringify(selectedRun.results ?? {}, null, 2)}</code>
                  </pre>
                </div>

                {selectedRun.error_message ? (
                  <div className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-red-400">
                    <p className="text-xs uppercase tracking-wide">Error</p>
                    <p className="mt-1 text-sm">{selectedRun.error_message}</p>
                  </div>
                ) : null}
              </div>
            )}
          </aside>
        </div>
      ) : null}
    </section>
  );
}
