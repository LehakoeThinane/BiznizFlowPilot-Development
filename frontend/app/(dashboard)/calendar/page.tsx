"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";

interface LeaveRequest {
  id: string;
  employee_name: string;
  start_date: string;
  end_date: string;
  status: string;
  leave_type_name: string | null;
}
interface LeaveListResp { items: LeaveRequest[]; total: number }

interface CalTask {
  id: string;
  title: string;
  due_date: string | null;
  status: string;
  priority: string;
}
interface TaskListResp { items: CalTask[]; total: number }

type CalEvent =
  | { kind: "leave"; data: LeaveRequest }
  | { kind: "task";  data: CalTask };

const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const DAYS = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function buildGrid(year: number, month: number): Date[][] {
  const firstDay = new Date(year, month, 1);
  const startDow = firstDay.getDay();
  const weeks: Date[][] = [];
  const cur = new Date(year, month, 1 - startDow);
  for (let w = 0; w < 6; w++) {
    const week: Date[] = [];
    for (let d = 0; d < 7; d++) {
      week.push(new Date(cur));
      cur.setDate(cur.getDate() + 1);
    }
    weeks.push(week);
    if (cur.getMonth() > month || (cur.getFullYear() > year && month === 11)) {
      if (cur.getDay() === 0) break;
    }
  }
  return weeks;
}

function leaveColor(status: string): string {
  if (status === "approved")  return "bg-emerald-600/30 text-emerald-200 border border-emerald-600/40";
  if (status === "pending")   return "bg-amber-600/30 text-amber-200 border border-amber-600/40";
  if (status === "rejected")  return "bg-rose-600/30 text-rose-200 border border-rose-600/40";
  return "bg-slate-600/30 text-slate-300 border border-slate-600/40";
}

function taskColor(status: string, priority: string): string {
  if (status === "completed") return "bg-slate-600/30 text-slate-400 border border-slate-600/40";
  if (status === "overdue" || priority === "urgent")
    return "bg-rose-600/30 text-rose-200 border border-rose-600/40";
  if (priority === "high")    return "bg-orange-600/30 text-orange-200 border border-orange-600/40";
  return "bg-blue-600/30 text-blue-200 border border-blue-600/40";
}

export default function CalendarPage() {
  const now = new Date();
  const [year, setYear]   = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [tasks, setTasks]   = useState<CalTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Date | null>(null);

  const token = getStoredToken();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [leaveResp, taskResp] = await Promise.all([
        apiRequest<LeaveListResp>("/api/v1/hr/leave-requests?limit=200", { authToken: token }),
        apiRequest<TaskListResp>("/api/v1/tasks?limit=200", { authToken: token }),
      ]);
      setLeaves(leaveResp.items ?? []);
      setTasks(taskResp.items ?? []);
    } catch (e: unknown) {
      setLeaves([]);
      setTasks([]);
      setError(e instanceof Error ? e.message : "Failed to load calendar data");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const grid = useMemo(() => buildGrid(year, month), [year, month]);

  const todayStr = toDateStr(now);

  function eventsForDay(day: Date): CalEvent[] {
    const ds = toDateStr(day);
    const result: CalEvent[] = [];
    for (const leave of leaves) {
      if (ds >= leave.start_date && ds <= leave.end_date) {
        result.push({ kind: "leave", data: leave });
      }
    }
    for (const task of tasks) {
      if (task.due_date && task.due_date.slice(0, 10) === ds) {
        result.push({ kind: "task", data: task });
      }
    }
    return result;
  }

  function prevMonth() {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
    setSelected(null);
  }

  function nextMonth() {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
    setSelected(null);
  }

  const selectedEvents = selected ? eventsForDay(selected) : [];
  const selectedStr = selected ? toDateStr(selected) : null;

  return (
    <div className="flex flex-col gap-5 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Calendar</h1>
          <p className="mt-1 text-xs text-slate-400">
            Leave requests and task due dates
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={prevMonth}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5 transition-colors"
          >
            ‹
          </button>
          <span className="w-36 text-center text-sm font-semibold text-white">
            {MONTHS[month]} {year}
          </span>
          <button
            type="button"
            onClick={nextMonth}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5 transition-colors"
          >
            ›
          </button>
          <button
            type="button"
            onClick={() => { setYear(now.getFullYear()); setMonth(now.getMonth()); setSelected(null); }}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5 transition-colors"
          >
            Today
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {[
          { label: "Leave – Approved", cls: "bg-emerald-600/30 border border-emerald-600/40 text-emerald-200" },
          { label: "Leave – Pending",  cls: "bg-amber-600/30 border border-amber-600/40 text-amber-200" },
          { label: "Task – Normal",    cls: "bg-blue-600/30 border border-blue-600/40 text-blue-200" },
          { label: "Task – Urgent",    cls: "bg-rose-600/30 border border-rose-600/40 text-rose-200" },
        ].map(({ label, cls }) => (
          <span key={label} className={`rounded-full px-2 py-0.5 ${cls}`}>{label}</span>
        ))}
      </div>
      {error && (
        <div className="rounded-lg border border-red-900/40 bg-red-950/30 px-4 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="flex gap-5">
        {/* Calendar grid */}
        <div className="min-w-0 flex-1 rounded-xl border border-white/6 bg-[#1e293b] overflow-hidden">
          {/* Day headers */}
          <div className="grid grid-cols-7 border-b border-white/6">
            {DAYS.map((d) => (
              <div key={d} className="px-2 py-2 text-center text-xs font-medium text-slate-500">
                {d}
              </div>
            ))}
          </div>

          {loading ? (
            <div className="px-5 py-12 text-center text-sm text-slate-400">Loading…</div>
          ) : (
            <div>
              {grid.map((week, wi) => (
                <div key={wi} className="grid grid-cols-7 border-b border-white/4 last:border-b-0">
                  {week.map((day) => {
                    const ds = toDateStr(day);
                    const isToday    = ds === todayStr;
                    const isCurMonth = day.getMonth() === month;
                    const isSelected = ds === selectedStr;
                    const dayEvents  = eventsForDay(day);
                    const overflow   = dayEvents.length > 2;
                    const shown      = dayEvents.slice(0, 2);

                    return (
                      <button
                        key={ds}
                        type="button"
                        onClick={() => setSelected(isSelected ? null : day)}
                        className={[
                          "flex flex-col gap-0.5 p-2 text-left transition-colors min-h-[80px] border-r border-white/4 last:border-r-0",
                          isCurMonth ? "hover:bg-white/3" : "opacity-40 hover:bg-white/2",
                          isSelected ? "bg-blue-900/30" : "",
                        ].join(" ")}
                      >
                        <span className={[
                          "mb-0.5 flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium",
                          isToday
                            ? "bg-blue-600 text-white"
                            : isCurMonth ? "text-slate-200" : "text-slate-600",
                        ].join(" ")}>
                          {day.getDate()}
                        </span>
                        {shown.map((ev, i) => (
                          <span
                            key={i}
                            className={[
                              "block truncate rounded px-1 py-px text-[10px] leading-tight",
                              ev.kind === "leave"
                                ? leaveColor(ev.data.status)
                                : taskColor((ev.data as CalTask).status, (ev.data as CalTask).priority),
                            ].join(" ")}
                          >
                            {ev.kind === "leave"
                              ? ev.data.employee_name
                              : (ev.data as CalTask).title}
                          </span>
                        ))}
                        {overflow && (
                          <span className="text-[10px] text-slate-500">
                            +{dayEvents.length - 2} more
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Day detail panel */}
        {selected && (
          <aside className="w-72 shrink-0 rounded-xl border border-white/6 bg-[#1e293b] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">
                {selected.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
              </h2>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="text-slate-500 hover:text-slate-300 text-lg leading-none"
              >
                ×
              </button>
            </div>

            {selectedEvents.length === 0 ? (
              <p className="text-xs text-slate-500">Nothing scheduled.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {selectedEvents.map((ev, i) => (
                  <div
                    key={i}
                    className={[
                      "rounded-lg p-3 text-xs",
                      ev.kind === "leave"
                        ? leaveColor(ev.data.status)
                        : taskColor((ev.data as CalTask).status, (ev.data as CalTask).priority),
                    ].join(" ")}
                  >
                    {ev.kind === "leave" ? (
                      <>
                        <p className="font-semibold">{ev.data.employee_name}</p>
                        <p className="mt-0.5 opacity-80">
                          {ev.data.leave_type_name ?? "Leave"} · {ev.data.status}
                        </p>
                        <p className="mt-0.5 opacity-70">
                          {ev.data.start_date} → {ev.data.end_date}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="font-semibold">{(ev.data as CalTask).title}</p>
                        <p className="mt-0.5 opacity-80 capitalize">
                          {(ev.data as CalTask).priority} priority · {(ev.data as CalTask).status.replace("_", " ")}
                        </p>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
