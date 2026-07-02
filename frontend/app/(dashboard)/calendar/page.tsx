"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { useUser } from "@/contexts/UserContext";
import { CallPanel } from "@/components/CallPanel";
import type { Meeting, MeetingCallType, MeetingListResponse } from "@/types/api";

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

interface OrgUser { id: string; email: string; first_name: string; last_name: string }
interface OrgUserListResp { items: OrgUser[]; total: number }

type CalEvent =
  | { kind: "leave"; data: LeaveRequest }
  | { kind: "task";  data: CalTask }
  | { kind: "meeting"; data: Meeting };

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

function eventColor(ev: CalEvent): string {
  if (ev.kind === "leave") return leaveColor(ev.data.status);
  if (ev.kind === "task") return taskColor(ev.data.status, ev.data.priority);
  return meetingColor(ev.data.status);
}
function eventLabel(ev: CalEvent): string {
  if (ev.kind === "leave") return ev.data.employee_name;
  if (ev.kind === "task") return ev.data.title;
  return ev.data.title;
}

function meetingColor(status: string): string {
  if (status === "in_progress") return "bg-emerald-600/30 text-emerald-200 border border-emerald-600/40";
  if (status === "completed")   return "bg-slate-600/30 text-slate-400 border border-slate-600/40";
  if (status === "cancelled")   return "bg-slate-700/30 text-slate-500 border border-slate-700/40 line-through";
  return "bg-violet-600/30 text-violet-200 border border-violet-600/40";
}

interface ScheduleForm {
  title: string;
  description: string;
  start: string;
  end: string;
  call_type: MeetingCallType;
  participant_user_ids: string[];
}
const EMPTY_SCHEDULE: ScheduleForm = {
  title: "", description: "", start: "", end: "", call_type: "video", participant_user_ids: [],
};

const INPUT = "erp-input w-full px-3 py-2 text-sm";
const SELECT = `${INPUT} appearance-none [&>option]:bg-[#0f1c33] [&>option]:text-white`;

export default function CalendarPage() {
  const now = new Date();
  const { user } = useUser();
  const [year, setYear]   = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [leaves, setLeaves]     = useState<LeaveRequest[]>([]);
  const [tasks, setTasks]       = useState<CalTask[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [orgUsers, setOrgUsers] = useState<OrgUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Date | null>(null);

  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleForm, setScheduleForm] = useState<ScheduleForm>(EMPTY_SCHEDULE);
  const [scheduling, setScheduling] = useState(false);
  const [scheduleError, setScheduleError] = useState("");

  const [activeCall, setActiveCall] = useState<{ meetingId: string; callType: MeetingCallType; isOrganizer: boolean } | null>(null);
  const [incomingCalls, setIncomingCalls] = useState<Meeting[]>([]);

  const token = getStoredToken();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [leaveResp, taskResp, meetingResp] = await Promise.all([
        apiRequest<LeaveListResp>("/api/v1/hr/leave-requests?limit=200", { authToken: token }),
        apiRequest<TaskListResp>("/api/v1/tasks?limit=200", { authToken: token }),
        apiRequest<MeetingListResponse>("/api/v1/meetings?limit=200", { authToken: token }),
      ]);
      setLeaves(leaveResp.items ?? []);
      setTasks(taskResp.items ?? []);
      setMeetings(meetingResp.items ?? []);
    } catch (e: unknown) {
      setLeaves([]);
      setTasks([]);
      setMeetings([]);
      setError(e instanceof Error ? e.message : "Failed to load calendar data");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    apiRequest<OrgUserListResp>("/api/v1/users", { authToken: token })
      .then((d) => setOrgUsers((d.items ?? []).filter((u) => u.id !== user?.user_id)))
      .catch(() => setOrgUsers([]));
  }, [token, user]);

  // Poll for in-progress meetings the current user hasn't joined yet, to surface an incoming-call banner.
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const active = await apiRequest<Meeting[]>("/api/v1/meetings/active", { authToken: token });
        if (!cancelled) setIncomingCalls(active ?? []);
      } catch {
        if (!cancelled) setIncomingCalls([]);
      }
    }
    void poll();
    const interval = setInterval(poll, 30_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [token]);

  function set(field: keyof ScheduleForm, value: string) {
    setScheduleForm((f) => ({ ...f, [field]: value }));
  }

  function toggleAttendee(userId: string) {
    setScheduleForm((f) => ({
      ...f,
      participant_user_ids: f.participant_user_ids.includes(userId)
        ? f.participant_user_ids.filter((id) => id !== userId)
        : [...f.participant_user_ids, userId],
    }));
  }

  async function handleSchedule(e: React.FormEvent) {
    e.preventDefault();
    if (!scheduleForm.title.trim() || !scheduleForm.start || !scheduleForm.end || scheduleForm.participant_user_ids.length === 0) {
      setScheduleError("Title, start/end time, and at least one attendee are required.");
      return;
    }
    setScheduling(true);
    setScheduleError("");
    try {
      await apiRequest("/api/v1/meetings", {
        method: "POST",
        authToken: token,
        body: {
          title: scheduleForm.title.trim(),
          description: scheduleForm.description.trim() || null,
          start_time: new Date(scheduleForm.start).toISOString(),
          end_time: new Date(scheduleForm.end).toISOString(),
          call_type: scheduleForm.call_type,
          participant_user_ids: scheduleForm.participant_user_ids,
        },
      });
      setShowScheduleModal(false);
      setScheduleForm(EMPTY_SCHEDULE);
      void load();
    } catch (err: unknown) {
      setScheduleError(err instanceof Error ? err.message : "Failed to schedule meeting.");
    } finally {
      setScheduling(false);
    }
  }

  async function respondToMeeting(meetingId: string, response_status: "accepted" | "declined") {
    try {
      await apiRequest(`/api/v1/meetings/${meetingId}/respond`, {
        method: "POST", authToken: token, body: { response_status },
      });
      void load();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to respond to meeting.");
    }
  }

  async function startCall(meeting: Meeting) {
    try {
      await apiRequest(`/api/v1/meetings/${meeting.id}/start`, { method: "POST", authToken: token });
      setActiveCall({ meetingId: meeting.id, callType: meeting.call_type, isOrganizer: true });
      void load();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to start call.");
    }
  }

  function joinCall(meeting: Meeting) {
    setActiveCall({
      meetingId: meeting.id,
      callType: meeting.call_type,
      isOrganizer: meeting.organizer_id === user?.user_id,
    });
  }

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
    for (const meeting of meetings) {
      if (meeting.start_time.slice(0, 10) === ds) {
        result.push({ kind: "meeting", data: meeting });
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
      {/* Incoming call banner */}
      {incomingCalls.filter((m) => !activeCall || m.id !== activeCall.meetingId).map((m) => (
        <div key={m.id} className="flex items-center justify-between rounded-lg border border-emerald-600/40 bg-emerald-950/30 px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-emerald-200">Call in progress: {m.title}</p>
            <p className="text-xs text-emerald-300/70">{m.organizer_name} started this {m.call_type} call.</p>
          </div>
          <button
            type="button"
            onClick={() => joinCall(m)}
            className="erp-button-primary px-4 py-1.5 text-sm font-medium"
          >
            Join
          </button>
        </div>
      ))}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Calendar</h1>
          <p className="mt-1 text-xs text-slate-400">
            Leave requests, task due dates, and meetings
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => { setShowScheduleModal(true); setScheduleForm(EMPTY_SCHEDULE); setScheduleError(""); }}
            className="erp-button-primary px-4 py-2 text-sm font-medium transition-colors"
          >
            + Schedule Meeting
          </button>
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
          { label: "Meeting",          cls: "bg-violet-600/30 border border-violet-600/40 text-violet-200" },
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
                              eventColor(ev),
                            ].join(" ")}
                          >
                            {eventLabel(ev)}
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
                  <div key={i} className={["rounded-lg p-3 text-xs", eventColor(ev)].join(" ")}>
                    {ev.kind === "leave" && (
                      <>
                        <p className="font-semibold">{ev.data.employee_name}</p>
                        <p className="mt-0.5 opacity-80">
                          {ev.data.leave_type_name ?? "Leave"} · {ev.data.status}
                        </p>
                        <p className="mt-0.5 opacity-70">
                          {ev.data.start_date} → {ev.data.end_date}
                        </p>
                      </>
                    )}
                    {ev.kind === "task" && (
                      <>
                        <p className="font-semibold">{ev.data.title}</p>
                        <p className="mt-0.5 opacity-80 capitalize">
                          {ev.data.priority} priority · {ev.data.status.replace("_", " ")}
                        </p>
                      </>
                    )}
                    {ev.kind === "meeting" && (() => {
                      const meeting = ev.data;
                      const isOrganizer = meeting.organizer_id === user?.user_id;
                      const myParticipant = meeting.participants.find((p) => p.user_id === user?.user_id);
                      const time = new Date(meeting.start_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
                      return (
                        <>
                          <p className="font-semibold">{meeting.title}</p>
                          <p className="mt-0.5 opacity-80 capitalize">
                            {meeting.call_type} call · {time} · {meeting.status.replace("_", " ")}
                          </p>
                          <p className="mt-0.5 opacity-70">Organizer: {meeting.organizer_name}</p>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {meeting.status === "scheduled" && isOrganizer && (
                              <button type="button" onClick={() => startCall(meeting)} className="rounded-md bg-emerald-600 px-2 py-1 font-medium text-white hover:bg-emerald-500">
                                Start Call
                              </button>
                            )}
                            {meeting.status === "in_progress" && (
                              <button type="button" onClick={() => joinCall(meeting)} className="rounded-md bg-emerald-600 px-2 py-1 font-medium text-white hover:bg-emerald-500">
                                Join
                              </button>
                            )}
                            {!isOrganizer && myParticipant?.response_status === "pending" && meeting.status === "scheduled" && (
                              <>
                                <button type="button" onClick={() => respondToMeeting(meeting.id, "accepted")} className="rounded-md bg-white/10 px-2 py-1 font-medium text-white hover:bg-white/20">
                                  Accept
                                </button>
                                <button type="button" onClick={() => respondToMeeting(meeting.id, "declined")} className="rounded-md bg-white/10 px-2 py-1 font-medium text-white hover:bg-white/20">
                                  Decline
                                </button>
                              </>
                            )}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>

      {/* ── Schedule Meeting Modal ─────────────────────────────────────────── */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">Schedule Meeting</h2>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setShowScheduleModal(false)}
                className="text-slate-400 hover:text-white"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleSchedule} noValidate>
              <div className="max-h-[70vh] space-y-4 overflow-y-auto px-6 py-5">
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">Title *</label>
                  <input className={INPUT} value={scheduleForm.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Sprint Planning" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">Description</label>
                  <textarea rows={2} className={`${INPUT} resize-none`} value={scheduleForm.description} onChange={(e) => set("description", e.target.value)} placeholder="Optional agenda…" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-400">Start *</label>
                    <input type="datetime-local" className={INPUT} value={scheduleForm.start} onChange={(e) => set("start", e.target.value)} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-400">End *</label>
                    <input type="datetime-local" className={INPUT} value={scheduleForm.end} onChange={(e) => set("end", e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">Call Type</label>
                  <select aria-label="Call Type" className={SELECT} value={scheduleForm.call_type} onChange={(e) => set("call_type", e.target.value)}>
                    <option value="video">Video</option>
                    <option value="voice">Voice</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">Attendees *</label>
                  <div className="max-h-40 overflow-y-auto rounded-lg border border-outline-variant/60 p-2">
                    {orgUsers.length === 0 ? (
                      <p className="px-2 py-1 text-xs text-slate-500">No other users in this business yet.</p>
                    ) : (
                      orgUsers.map((u) => (
                        <label key={u.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-slate-200 hover:bg-white/5">
                          <input
                            type="checkbox"
                            checked={scheduleForm.participant_user_ids.includes(u.id)}
                            onChange={() => toggleAttendee(u.id)}
                          />
                          {u.first_name} {u.last_name} <span className="text-xs text-slate-500">({u.email})</span>
                        </label>
                      ))
                    )}
                  </div>
                </div>
                {scheduleError && (
                  <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-400">{scheduleError}</p>
                )}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/8 px-6 py-4">
                <button type="button" onClick={() => setShowScheduleModal(false)} className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={scheduling} className="erp-button-primary px-5 py-2 text-sm font-medium disabled:opacity-50 transition-colors">
                  {scheduling ? "Scheduling…" : "Schedule Meeting"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Active Call ────────────────────────────────────────────────────── */}
      {activeCall && (() => {
        const meeting = meetings.find((m) => m.id === activeCall.meetingId);
        return (
          <CallPanel
            meetingId={activeCall.meetingId}
            callType={activeCall.callType}
            participants={meeting?.participants ?? []}
            isOrganizer={activeCall.isOrganizer}
            onClose={() => { setActiveCall(null); void load(); }}
          />
        );
      })()}
    </div>
  );
}
