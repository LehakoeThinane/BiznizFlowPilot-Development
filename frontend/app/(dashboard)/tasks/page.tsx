"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError, apiRequest } from "@/lib/api";
import { getCurrentUser, getStoredToken, logout } from "@/lib/auth";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type {
  BusinessUser,
  BusinessUserListResponse,
  CurrentUser,
  Task,
  TaskListResponse,
} from "@/types/api";

type TaskStatusUi = "all" | "pending" | "in_progress" | "completed" | "overdue";
type TaskPriorityUi = "all" | "low" | "medium" | "high";
type TaskSortField =
  | "title"
  | "description"
  | "status"
  | "priority"
  | "assignedTo"
  | "dueDate"
  | "created";
type SortDirection = "asc" | "desc";

interface TaskEditorState {
  title: string;
  description: string;
  status: Exclude<TaskStatusUi, "all">;
  priority: Exclude<TaskPriorityUi, "all">;
  assigneeIds: string[];
  dueDate: string;
}

const PAGE_SIZE = 20;
const BOARD_PAGE_SIZE = 200;
const STATUS_COLUMNS: { key: Exclude<TaskStatusUi, "all">; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
  { key: "overdue", label: "Overdue" },
];

function toUiStatus(status: Task["status"]): Exclude<TaskStatusUi, "all"> {
  return status;
}

function toBackendStatus(status: Exclude<TaskStatusUi, "all">): Task["status"] {
  return status;
}

function toUiPriority(priority: Task["priority"]): Exclude<TaskPriorityUi, "all"> {
  if (priority === "urgent") {
    return "high";
  }
  return priority;
}

function toBackendPriority(priority: Exclude<TaskPriorityUi, "all">): Task["priority"] {
  return priority;
}

function statusBadgeClass(status: Exclude<TaskStatusUi, "all">): string {
  if (status === "pending")     return "bg-white/10 text-slate-400";
  if (status === "in_progress") return "bg-blue-500/20 text-blue-300";
  if (status === "completed")   return "bg-emerald-500/20 text-emerald-300";
  return "bg-amber-500/20 text-amber-300"; // overdue
}

function priorityBadgeClass(priority: Exclude<TaskPriorityUi, "all">): string {
  if (priority === "low") return "bg-white/10 text-slate-400";
  if (priority === "medium") return "bg-amber-500/20 text-amber-300";
  return "bg-rose-500/20 text-rose-300";
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

function toInputDateTime(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function truncate(text: string | null | undefined, max = 80): string {
  const value = (text ?? "").trim();
  if (!value) return "-";
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

function defaultEditor(): TaskEditorState {
  return {
    title: "",
    description: "",
    status: "pending",
    priority: "medium",
    assigneeIds: [],
    dueDate: "",
  };
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
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

export default function TasksPage() {
  const [viewMode, setViewMode] = useState<"list" | "board">("board");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<TaskStatusUi>("all");
  const [priorityFilter, setPriorityFilter] = useState<TaskPriorityUi>("all");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sortField, setSortField] = useState<TaskSortField>("created");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [bulkStatus, setBulkStatus] = useState<Exclude<TaskStatusUi, "all">>("in_progress");
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);

  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [businessUsers, setBusinessUsers] = useState<BusinessUser[]>([]);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSavingCreate, setIsSavingCreate] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [editor, setEditor] = useState<TaskEditorState>(defaultEditor());

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const visibleTasks = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = tasks.filter((task) => {
      const titleMatch = task.title.toLowerCase().includes(query);
      const priorityMatch =
        priorityFilter === "all" || toUiPriority(task.priority) === priorityFilter;
      return titleMatch && priorityMatch;
    });

    filtered.sort((left, right) => {
      if (sortField === "title") {
        return left.title.localeCompare(right.title);
      }
      if (sortField === "description") {
        return (left.description ?? "").localeCompare(right.description ?? "");
      }
      if (sortField === "status") {
        return toUiStatus(left.status).localeCompare(toUiStatus(right.status));
      }
      if (sortField === "priority") {
        return toUiPriority(left.priority).localeCompare(toUiPriority(right.priority));
      }
      if (sortField === "assignedTo") {
        return (left.assigned_to ?? "").localeCompare(right.assigned_to ?? "");
      }
      if (sortField === "dueDate") {
        return new Date(left.due_date ?? "").getTime() - new Date(right.due_date ?? "").getTime();
      }
      return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
    });

    if (sortDirection === "desc") {
      filtered.reverse();
    }

    return filtered;
  }, [priorityFilter, search, sortDirection, sortField, tasks]);

  // Board columns ARE the status split, so this applies search + priority
  // only, leaving status filtering to the column grouping itself.
  const boardTasks = useMemo(() => {
    const query = search.trim().toLowerCase();
    return tasks.filter((task) => {
      const titleMatch = task.title.toLowerCase().includes(query);
      const priorityMatch =
        priorityFilter === "all" || toUiPriority(task.priority) === priorityFilter;
      return titleMatch && priorityMatch;
    });
  }, [priorityFilter, search, tasks]);

  const visibleTaskIdSet = useMemo(
    () => new Set(visibleTasks.map((task) => task.id)),
    [visibleTasks],
  );

  const selectedVisibleTaskIds = useMemo(
    () => selectedTaskIds.filter((taskId) => visibleTaskIdSet.has(taskId)),
    [selectedTaskIds, visibleTaskIdSet],
  );

  const allVisibleSelected =
    visibleTasks.length > 0 && selectedVisibleTaskIds.length === visibleTasks.length;

  const assigneeOptions = useMemo(() => {
    return businessUsers.map((user) => {
      const fullName = `${user.first_name} ${user.last_name}`.trim();
      const label = fullName ? `${fullName} (${user.email})` : user.email;
      return { id: user.id, label };
    });
  }, [businessUsers]);

  const resolveAssignee = useCallback(
    (assignedTo: string | null): string => {
      if (!assignedTo) return "-";
      const match = assigneeOptions.find((option) => option.id === assignedTo);
      if (match) return match.label;
      if (currentUser && currentUser.user_id === assignedTo) return currentUser.email;
      return `${assignedTo.slice(0, 8)}…`;
    },
    [assigneeOptions, currentUser],
  );

  const resolveAssignees = useCallback(
    (assigneeIds: string[] | null | undefined): string => {
      if (!assigneeIds || assigneeIds.length === 0) return "-";
      return assigneeIds.map((id) => resolveAssignee(id)).join(", ");
    },
    [resolveAssignee],
  );

  const hydrateEditorFromTask = useCallback((task: Task) => {
    setEditor({
      title: task.title,
      description: task.description ?? "",
      status: toUiStatus(task.status),
      priority: toUiPriority(task.priority),
      assigneeIds: task.assignee_ids?.length ? task.assignee_ids : task.assigned_to ? [task.assigned_to] : [],
      dueDate: toInputDateTime(task.due_date),
    });
  }, []);

  const loadTasks = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsLoading(true);
    setError(null);

    // The board shows every status split into columns at once, so it needs
    // a much wider fetch and must ignore the list's single-status filter
    // (which would otherwise leave most columns empty).
    const skip = viewMode === "board" ? 0 : (page - 1) * PAGE_SIZE;
    const limit = viewMode === "board" ? BOARD_PAGE_SIZE : PAGE_SIZE;
    const statusQuery =
      viewMode === "board" || statusFilter === "all"
        ? ""
        : `&status=${encodeURIComponent(toBackendStatus(statusFilter))}`;

    try {
      const [taskResponse, userResponse, usersResponse] = await Promise.all([
        apiRequest<TaskListResponse>(
          `/api/v1/tasks?skip=${skip}&limit=${limit}${statusQuery}`,
          {
            method: "GET",
            authToken: token,
          },
        ),
        getCurrentUser(),
        apiRequest<BusinessUserListResponse>("/api/v1/users?skip=0&limit=200", {
          method: "GET",
          authToken: token,
        }).catch(() => ({ total: 0, items: [] })),
      ]);

      setTasks(taskResponse.items);
      setTotal(taskResponse.total);
      setCurrentUser(userResponse);
      setBusinessUsers(usersResponse.items);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to load tasks.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, viewMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadTasks();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTasks]);

  const searchParams = useSearchParams();
  useEffect(() => {
    const openId = searchParams.get("open");
    if (openId) {
      void openTaskDetails({ id: openId } as Task);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSortChange = useCallback((field: TaskSortField) => {
    setSortField((previousField) => {
      if (previousField === field) {
        setSortDirection((previousDirection) =>
          previousDirection === "asc" ? "desc" : "asc",
        );
        return previousField;
      }
      setSortDirection(field === "created" ? "desc" : "asc");
      return field;
    });
  }, []);

  const handleToggleAllVisible = useCallback(() => {
    if (visibleTasks.length === 0) {
      return;
    }

    setSelectedTaskIds((previous) => {
      if (allVisibleSelected) {
        const visible = new Set(visibleTasks.map((task) => task.id));
        return previous.filter((taskId) => !visible.has(taskId));
      }

      const merged = new Set(previous);
      for (const task of visibleTasks) {
        merged.add(task.id);
      }
      return Array.from(merged);
    });
  }, [allVisibleSelected, visibleTasks]);

  const handleToggleOne = useCallback((taskId: string) => {
    setSelectedTaskIds((previous) => {
      if (previous.includes(taskId)) {
        return previous.filter((id) => id !== taskId);
      }
      return [...previous, taskId];
    });
  }, []);

  const handleDropTask = useCallback(
    async (taskId: string, newStatus: Exclude<TaskStatusUi, "all">) => {
      const task = tasks.find((candidate) => candidate.id === taskId);
      if (!task || task.status === newStatus) {
        return;
      }

      const token = getStoredToken();
      if (!token) {
        logout();
        window.location.replace("/login");
        return;
      }

      // Optimistic update - the board should feel instant even though this
      // VM's response times can vary; revert on failure below.
      const previousTasks = tasks;
      setTasks((current) =>
        current.map((candidate) =>
          candidate.id === taskId ? { ...candidate, status: newStatus } : candidate,
        ),
      );
      setError(null);

      try {
        await apiRequest<Task>(`/api/v1/tasks/${taskId}`, {
          method: "PATCH",
          authToken: token,
          body: { status: toBackendStatus(newStatus) },
        });
      } catch (requestError) {
        setTasks(previousTasks);
        if (requestError instanceof ApiError && requestError.status === 401) {
          logout();
          window.location.replace("/login");
          return;
        }
        setError(
          toErrorMessage(requestError, "Unable to move that task - it may not be yours to update."),
        );
      }
    },
    [tasks],
  );

  const handleBulkStatusUpdate = useCallback(async () => {
    if (selectedVisibleTaskIds.length === 0) {
      return;
    }

    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsBulkUpdating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const outcomes = await Promise.allSettled(
        selectedVisibleTaskIds.map((taskId) =>
          apiRequest<Task>(`/api/v1/tasks/${taskId}`, {
            method: "PATCH",
            authToken: token,
            body: {
              status: toBackendStatus(bulkStatus),
            },
          }),
        ),
      );

      const successCount = outcomes.filter((outcome) => outcome.status === "fulfilled").length;
      const failureCount = outcomes.length - successCount;

      if (successCount > 0) {
        setSuccessMessage(
          `Updated ${successCount} task${successCount === 1 ? "" : "s"} to ${bulkStatus}.`,
        );
        setSelectedTaskIds((previous) =>
          previous.filter((taskId) => !selectedVisibleTaskIds.includes(taskId)),
        );
        await loadTasks();
      }

      if (failureCount > 0) {
        const firstFailure = outcomes.find(
          (outcome): outcome is PromiseRejectedResult => outcome.status === "rejected",
        );
        setError(
          `${toErrorMessage(firstFailure?.reason, "Unable to update selected tasks.")} (${failureCount} failed${successCount > 0 ? `, ${successCount} succeeded` : ""})`,
        );
      }
    } finally {
      setIsBulkUpdating(false);
    }
  }, [bulkStatus, loadTasks, selectedVisibleTaskIds]);

  const exportVisibleTasksCsv = useCallback(() => {
    if (visibleTasks.length === 0) {
      return;
    }

    const rows: string[][] = [
      [
        "Task ID",
        "Title",
        "Description",
        "Status",
        "Priority",
        "Assigned To",
        "Due Date",
        "Created",
      ],
    ];

    for (const task of visibleTasks) {
      rows.push([
        task.id,
        task.title,
        task.description ?? "",
        toUiStatus(task.status),
        toUiPriority(task.priority),
        resolveAssignees(task.assignee_ids),
        formatDate(task.due_date),
        formatDate(task.created_at),
      ]);
    }

    const datePart = new Date().toISOString().slice(0, 10);
    downloadCsv(`tasks-${datePart}.csv`, rows);
  }, [resolveAssignees, visibleTasks]);

  async function openTaskDetails(task: Task) {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setSelectedTask(task);
    setIsDetailsLoading(true);
    setIsEditing(false);
    setError(null);
    try {
      const fullTask = await apiRequest<Task>(`/api/v1/tasks/${task.id}`, {
        method: "GET",
        authToken: token,
      });
      setSelectedTask(fullTask);
      hydrateEditorFromTask(fullTask);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to load task details.",
      );
    } finally {
      setIsDetailsLoading(false);
    }
  }

  async function handleCreateTask() {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }
    if (!editor.title.trim()) {
      setError("Title is required.");
      return;
    }

    setIsSavingCreate(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<Task>("/api/v1/tasks", {
        method: "POST",
        authToken: token,
        body: {
              title: editor.title.trim(),
              description: editor.description.trim() || null,
              status: toBackendStatus(editor.status),
              priority: toBackendPriority(editor.priority),
              assignee_ids: editor.assigneeIds,
              due_date: editor.dueDate ? new Date(editor.dueDate).toISOString() : null,
            },
          });
      setIsCreateOpen(false);
      setEditor(defaultEditor());
      await loadTasks();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to create task.",
      );
    } finally {
      setIsSavingCreate(false);
    }
  }

  async function handleSaveTaskEdits() {
    if (!selectedTask) return;
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }
    if (!editor.title.trim()) {
      setError("Title is required.");
      return;
    }

    setIsSavingEdit(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiRequest<Task>(`/api/v1/tasks/${selectedTask.id}`, {
        method: "PATCH",
        authToken: token,
        body: {
              title: editor.title.trim(),
              description: editor.description.trim() || null,
              status: toBackendStatus(editor.status),
              priority: toBackendPriority(editor.priority),
              assignee_ids: editor.assigneeIds,
              due_date: editor.dueDate ? new Date(editor.dueDate).toISOString() : null,
            },
          });
      setSelectedTask(updated);
      setIsEditing(false);
      await loadTasks();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to update task.",
      );
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleDeleteTask() {
    if (!selectedTask) return;
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }
    setIsDeleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await apiRequest<{ message: string }>(`/api/v1/tasks/${selectedTask.id}`, {
        method: "DELETE",
        authToken: token,
      });
      setSelectedTask(null);
      setIsEditing(false);
      await loadTasks();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to delete task.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleMarkComplete() {
    if (!selectedTask) return;
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }
    setIsCompleting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updated = await apiRequest<Task>(`/api/v1/tasks/${selectedTask.id}`, {
        method: "PATCH",
        authToken: token,
        body: { status: "completed" },
      });
      setSelectedTask(updated);
      hydrateEditorFromTask(updated);
      await loadTasks();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to mark task complete.",
      );
    } finally {
      setIsCompleting(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Tasks</h1>
          <p className="mt-1 text-sm text-muted">
            Manage task lifecycle, assignments, and due dates.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-outline-variant p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("board")}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                viewMode === "board"
                  ? "bg-brand text-on-primary"
                  : "text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              Board
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                viewMode === "list"
                  ? "bg-brand text-on-primary"
                  : "text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              List
            </button>
          </div>
          <button
            type="button"
            className="erp-button-primary px-4 py-2 text-sm font-semibold"
            onClick={() => {
              setEditor(defaultEditor());
              setIsCreateOpen(true);
              setError(null);
            }}
          >
            Create Task
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search title"
          className="min-w-62.5 erp-input w-full px-3 py-2 text-sm"
        />
        <select
          aria-label="Filter by status"
          value={statusFilter}
          disabled={viewMode === "board"}
          title={viewMode === "board" ? "Board view already splits tasks by status" : undefined}
          onChange={(event) => {
            setStatusFilter(event.target.value as TaskStatusUi);
            setPage(1);
          }}
          className="erp-input w-full px-3 py-2 text-sm disabled:opacity-50"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="overdue">Overdue</option>
        </select>
        <select
          aria-label="Filter by priority"
          value={priorityFilter}
          onChange={(event) => setPriorityFilter(event.target.value as TaskPriorityUi)}
          className="erp-input w-full px-3 py-2 text-sm"
        >
          <option value="all">All priorities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high"
          onClick={() => void loadTasks()}
        >
          Refresh
        </button>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high disabled:opacity-50"
          onClick={exportVisibleTasksCsv}
          disabled={visibleTasks.length === 0}
        >
          Export CSV
        </button>
        <button
          type="button"
          className="rounded-md border border-outline-variant px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high"
          onClick={() => {
            setSearch("");
            setStatusFilter("all");
            setPriorityFilter("all");
            setSortField("created");
            setSortDirection("desc");
          }}
        >
          Clear
        </button>
      </div>

      <p className="text-sm text-muted">
        Showing {viewMode === "board" ? boardTasks.length : visibleTasks.length} of {tasks.length} task
        {tasks.length === 1 ? "" : "s"}.
      </p>

      {viewMode === "list" && selectedVisibleTaskIds.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-white/5 px-4 py-3 text-sm">
          <p className="text-[#aaa]">
            Selected {selectedVisibleTaskIds.length} task
            {selectedVisibleTaskIds.length === 1 ? "" : "s"}.
          </p>
          <div className="flex items-center gap-2">
            <select
              aria-label="Bulk status to apply"
              value={bulkStatus}
              onChange={(event) =>
                setBulkStatus(event.target.value as Exclude<TaskStatusUi, "all">)
              }
              className="rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-1.5 text-sm capitalize"
            >
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
            </select>
            <button
              type="button"
              className="rounded-md border border-blue-700/40 px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-blue-900/20 disabled:opacity-60"
              onClick={() => void handleBulkStatusUpdate()}
              disabled={isBulkUpdating}
            >
              {isBulkUpdating ? "Updating..." : "Apply Status"}
            </button>
          </div>
        </div>
      ) : null}

      {successMessage ? (
        <div className="rounded-md border border-emerald-900/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-400">
          {successMessage}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button
            type="button"
            className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium text-red-400 hover:bg-red-900/20"
            onClick={() => void loadTasks()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="erp-panel p-5 text-sm text-muted">
          Loading tasks...
        </div>
      ) : viewMode === "board" ? (
        <TaskBoard
          tasks={boardTasks}
          onOpenTask={(task) => void openTaskDetails(task)}
          onDropTask={(taskId, newStatus) => void handleDropTask(taskId, newStatus)}
          resolveAssignees={resolveAssignees}
        />
      ) : visibleTasks.length === 0 ? (
        <div className="erp-panel p-5 text-sm text-muted">
          No tasks found for the current filters.
        </div>
      ) : (
        <div className="overflow-x-auto erp-panel">
          <table className="min-w-full text-sm">
            <thead className="bg-[#111e35] text-left">
              <tr>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={handleToggleAllVisible}
                    aria-label="Select all visible tasks"
                  />
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("title")}
                  >
                    Title
                    <SortIndicator active={sortField === "title"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("description")}
                  >
                    Description
                    <SortIndicator
                      active={sortField === "description"}
                      direction={sortDirection}
                    />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("status")}
                  >
                    Status
                    <SortIndicator active={sortField === "status"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("priority")}
                  >
                    Priority
                    <SortIndicator active={sortField === "priority"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("assignedTo")}
                  >
                    Assigned To
                    <SortIndicator
                      active={sortField === "assignedTo"}
                      direction={sortDirection}
                    />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("dueDate")}
                  >
                    Due Date
                    <SortIndicator active={sortField === "dueDate"} direction={sortDirection} />
                  </button>
                </th>
                <th className="px-4 py-3 font-medium text-[#aaa]">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 hover:text-white/80"
                    onClick={() => handleSortChange("created")}
                  >
                    Created
                    <SortIndicator active={sortField === "created"} direction={sortDirection} />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleTasks.map((task) => {
                const status = toUiStatus(task.status);
                const priority = toUiPriority(task.priority);
                return (
                  <tr
                    key={task.id}
                    className="cursor-pointer border-t border-outline-variant/70 hover:bg-surface-container-high/70"
                    onClick={() => void openTaskDetails(task)}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedTaskIds.includes(task.id)}
                        onClick={(event) => event.stopPropagation()}
                        onChange={() => handleToggleOne(task.id)}
                        aria-label={`Select ${task.title}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-white">{task.title}</td>
                    <td className="px-4 py-3 text-[#aaa]">{truncate(task.description)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-1 text-xs font-semibold capitalize",
                          statusBadgeClass(status),
                        ].join(" ")}
                      >
                        {status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-1 text-xs font-semibold capitalize",
                          priorityBadgeClass(priority),
                        ].join(" ")}
                      >
                        {priority}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[#aaa]">{resolveAssignees(task.assignee_ids)}</td>
                    <td className="px-4 py-3 text-[#aaa]">{formatDate(task.due_date)}</td>
                    <td className="px-4 py-3 text-[#aaa]">{formatDate(task.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {viewMode === "list" ? (
        <div className="flex items-center justify-between text-sm text-[#aaa]">
          <p>
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-md border border-outline-variant bg-[#0c172b] px-3 py-1 disabled:opacity-50"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <button
              type="button"
              className="rounded-md border border-outline-variant bg-[#0c172b] px-3 py-1 disabled:opacity-50"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}

      {isCreateOpen ? (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => setIsCreateOpen(false)}
            aria-label="Close create task panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-[#0f1c33] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Create Task</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => setIsCreateOpen(false)}
              >
                Close
              </button>
            </div>
            <TaskForm
              editor={editor}
              onChange={setEditor}
              onSubmit={() => void handleCreateTask()}
              submitLabel={isSavingCreate ? "Creating..." : "Create Task"}
              disabled={isSavingCreate}
              assigneeOptions={assigneeOptions}
            />
          </aside>
        </div>
      ) : null}

      {selectedTask ? (
        <div className="fixed inset-0 z-40 flex">
          <button
            type="button"
            className="h-full flex-1 bg-slate-900/30"
            onClick={() => {
              setSelectedTask(null);
              setIsEditing(false);
            }}
            aria-label="Close task details panel"
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-outline-variant bg-[#0f1c33] p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Task Details</h2>
              <button
                type="button"
                className="rounded-md border border-outline-variant px-3 py-1 text-sm text-on-surface-variant hover:bg-surface-container-high"
                onClick={() => {
                  setSelectedTask(null);
                  setIsEditing(false);
                }}
              >
                Close
              </button>
            </div>

            {isDetailsLoading ? (
              <p className="text-sm text-muted">Loading task details...</p>
            ) : (
              <div className="space-y-4">
                {!isEditing ? (
                  <>
                    <div className="grid gap-3 text-sm sm:grid-cols-2">
                      <DetailItem label="Title" value={selectedTask.title} />
                      <DetailItem
                        label="Status"
                        value={toUiStatus(selectedTask.status)}
                        capitalize
                      />
                      <DetailItem
                        label="Priority"
                        value={toUiPriority(selectedTask.priority)}
                        capitalize
                      />
                      <DetailItem
                        label="Assigned To"
                        value={resolveAssignees(selectedTask.assignee_ids)}
                      />
                      <DetailItem label="Due Date" value={formatDate(selectedTask.due_date)} />
                      <DetailItem label="Created" value={formatDate(selectedTask.created_at)} />
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted">Description</p>
                      <p className="mt-1 rounded-md border border-border bg-white/5 p-3 text-sm text-[#ccc] whitespace-pre-wrap">
                        {selectedTask.description?.trim() || "No description"}
                      </p>
                    </div>

                    <ActivityTimeline entityType="task" entityId={selectedTask.id} />

                    <div className="flex flex-wrap gap-2">
                      {(selectedTask.status === "pending" ||
                        selectedTask.status === "in_progress") && (
                        <button
                          type="button"
                          className="rounded-md border border-emerald-700/40 px-4 py-2 text-sm font-semibold text-emerald-400 hover:bg-emerald-900/20 disabled:opacity-50"
                          disabled={isCompleting}
                          onClick={() => void handleMarkComplete()}
                        >
                          {isCompleting ? "Completing..." : "Mark Complete"}
                        </button>
                      )}
                      <button
                        type="button"
                        className="erp-button-primary px-4 py-2 text-sm font-semibold"
                        onClick={() => {
                          hydrateEditorFromTask(selectedTask);
                          setIsEditing(true);
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-red-800/40 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-900/20 disabled:opacity-50"
                        disabled={isDeleting}
                        onClick={() => void handleDeleteTask()}
                      >
                        {isDeleting ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <TaskForm
                      editor={editor}
                      onChange={setEditor}
                      onSubmit={() => void handleSaveTaskEdits()}
                      submitLabel={isSavingEdit ? "Saving..." : "Save"}
                      disabled={isSavingEdit}
                      assigneeOptions={assigneeOptions}
                    />
                    <button
                      type="button"
                      className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
                      onClick={() => {
                        if (selectedTask) hydrateEditorFromTask(selectedTask);
                        setIsEditing(false);
                      }}
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            )}
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function SortIndicator({
  active,
  direction,
}: {
  active: boolean;
  direction: SortDirection;
}) {
  if (!active) {
    return <span className="text-[#555]">↕</span>;
  }
  return <span>{direction === "asc" ? "↑" : "↓"}</span>;
}

function TaskBoard({
  tasks,
  onOpenTask,
  onDropTask,
  resolveAssignees,
}: {
  tasks: Task[];
  onOpenTask: (task: Task) => void;
  onDropTask: (taskId: string, newStatus: Exclude<TaskStatusUi, "all">) => void;
  resolveAssignees: (assigneeIds: string[] | null | undefined) => string;
}) {
  const [dragOverColumn, setDragOverColumn] = useState<Exclude<TaskStatusUi, "all"> | null>(null);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {STATUS_COLUMNS.map((column) => {
        const columnTasks = tasks.filter((task) => task.status === column.key);
        return (
          <div
            key={column.key}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOverColumn(column.key);
            }}
            onDragLeave={() =>
              setDragOverColumn((current) => (current === column.key ? null : current))
            }
            onDrop={(event) => {
              event.preventDefault();
              setDragOverColumn(null);
              const taskId = event.dataTransfer.getData("text/plain");
              if (taskId) onDropTask(taskId, column.key);
            }}
            className={`erp-panel flex min-h-50 flex-col gap-2 p-3 transition-colors ${
              dragOverColumn === column.key ? "ring-2 ring-brand" : ""
            }`}
          >
            <div className="mb-1 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">{column.label}</h3>
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-[#aaa]">
                {columnTasks.length}
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-2">
              {columnTasks.length === 0 ? (
                <p className="px-1 text-xs italic text-muted">No tasks</p>
              ) : (
                columnTasks.map((task) => {
                  const priority = toUiPriority(task.priority);
                  return (
                    <div
                      key={task.id}
                      draggable
                      onDragStart={(event) => {
                        event.dataTransfer.setData("text/plain", task.id);
                        event.dataTransfer.effectAllowed = "move";
                      }}
                      onClick={() => onOpenTask(task)}
                      className="cursor-grab rounded-md border border-border bg-white/5 p-3 text-sm hover:bg-white/[0.08] active:cursor-grabbing"
                    >
                      <p className="font-medium text-white">{task.title}</p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span
                          className={[
                            "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize",
                            priorityBadgeClass(priority),
                          ].join(" ")}
                        >
                          {priority}
                        </span>
                        <span className="truncate text-xs text-muted">
                          {resolveAssignees(task.assignee_ids)}
                        </span>
                      </div>
                      {task.due_date ? (
                        <p className="mt-1.5 text-xs text-muted">{formatDate(task.due_date)}</p>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DetailItem({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-sm text-[#ccc] ${capitalize ? "capitalize" : ""}`}>{value}</p>
    </div>
  );
}

function TaskForm({
  editor,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  assigneeOptions,
}: {
  editor: TaskEditorState;
  onChange: (next: TaskEditorState) => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
  assigneeOptions: Array<{ id: string; label: string }>;
}) {
  function update<K extends keyof TaskEditorState>(key: K, value: TaskEditorState[K]) {
    onChange({ ...editor, [key]: value });
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="task-title">
          Title
        </label>
        <input
          id="task-title"
          value={editor.title}
          onChange={(event) => update("title", event.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label
          className="mb-1 block text-sm font-medium text-[#aaa]"
          htmlFor="task-description"
        >
          Description
        </label>
        <textarea
          id="task-description"
          rows={4}
          value={editor.description}
          onChange={(event) => update("description", event.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="task-status">
            Status
          </label>
          <select
            id="task-status"
            value={editor.status}
            onChange={(event) =>
              update("status", event.target.value as Exclude<TaskStatusUi, "all">)
            }
            className="erp-input w-full px-3 py-2 text-sm"
          >
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <div>
          <label
            className="mb-1 block text-sm font-medium text-[#aaa]"
            htmlFor="task-priority"
          >
            Priority
          </label>
          <select
            id="task-priority"
            value={editor.priority}
            onChange={(event) =>
              update("priority", event.target.value as Exclude<TaskPriorityUi, "all">)
            }
            className="erp-input w-full px-3 py-2 text-sm"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]">
          Assigned To (optional, select any number of people)
        </label>
        <div className="max-h-40 overflow-y-auto rounded-md border border-border bg-white/5 p-2">
          {assigneeOptions.length === 0 ? (
            <p className="px-1 py-1 text-xs text-muted">No teammates to assign yet.</p>
          ) : (
            assigneeOptions.map((option) => {
              const checked = editor.assigneeIds.includes(option.id);
              return (
                <label
                  key={option.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-1 py-1.5 text-sm text-[#ddd] hover:bg-white/5"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      update(
                        "assigneeIds",
                        checked
                          ? editor.assigneeIds.filter((id) => id !== option.id)
                          : [...editor.assigneeIds, option.id],
                      )
                    }
                  />
                  {option.label}
                </label>
              );
            })
          )}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="task-due">
          Due Date (optional)
        </label>
        <input
          id="task-due"
          type="datetime-local"
          value={editor.dueDate}
          onChange={(event) => update("dueDate", event.target.value)}
          className="erp-input w-full px-3 py-2 text-sm"
        />
      </div>

      <button
        type="button"
        className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-60"
        onClick={onSubmit}
        disabled={disabled}
      >
        {submitLabel}
      </button>
    </div>
  );
}


