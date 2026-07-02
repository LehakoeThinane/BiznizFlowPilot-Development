"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import type { Workflow, WorkflowActionInput, WorkflowDefinitionInput } from "@/types/api";

type WorkflowActionType = "log" | "create_task" | "send_email" | "webhook";
type WebhookMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface ActionTypeOption {
  value: WorkflowActionType;
  label: string;
  description: string;
}

interface TriggerTypeOption {
  value: string;
  label: string;
  description: string;
}

interface ActionFormState {
  id: string;
  action_type: WorkflowActionType;
  message: string;
  title: string;
  assigned_to: string;
  recipient: string;
  subject: string;
  body_template: string;
  url: string;
  method: WebhookMethod;
}

interface ActionTemplate {
  id: string;
  name: string;
  description: string;
  action: Omit<ActionFormState, "id">;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  trigger_event_type: string;
  actions: Array<Omit<ActionFormState, "id">>;
}

const TRIGGER_OPTIONS: TriggerTypeOption[] = [
  {
    value: "lead_created",
    label: "Lead Created",
    description: "Runs when a new lead enters the system.",
  },
  {
    value: "lead_status_changed",
    label: "Lead Status Changed",
    description: "Runs whenever a lead moves to a different status.",
  },
  {
    value: "task_created",
    label: "Task Created",
    description: "Runs when a new task is created.",
  },
  {
    value: "task_completed",
    label: "Task Completed",
    description: "Runs when a task is marked as completed.",
  },
  {
    value: "workflow_triggered",
    label: "Workflow Triggered",
    description: "Runs in response to another workflow event.",
  },
  {
    value: "custom",
    label: "Custom Event",
    description: "Runs on a custom event type sent by integrations.",
  },
];

const ACTION_OPTIONS: ActionTypeOption[] = [
  {
    value: "log",
    label: "Log",
    description: "Write a structured message to workflow execution results.",
  },
  {
    value: "create_task",
    label: "Create Task",
    description: "Create a pending task for follow-up work.",
  },
  {
    value: "send_email",
    label: "Send Email",
    description: "Send an outbound email notification.",
  },
  {
    value: "webhook",
    label: "Webhook",
    description: "Call an external endpoint with an HTTP request.",
  },
];

const ACTION_TEMPLATE_LIBRARY: ActionTemplate[] = [
  {
    id: "template-log-audit",
    name: "Audit Log",
    description: "Record that the workflow executed for auditing.",
    action: {
      action_type: "log",
      message: "Workflow execution recorded.",
      title: "Follow up lead",
      assigned_to: "",
      recipient: "",
      subject: "Workflow notification",
      body_template: "Workflow completed.",
      url: "https://example.com/webhook",
      method: "POST",
    },
  },
  {
    id: "template-task-followup",
    name: "Lead Follow-Up Task",
    description: "Create a pending follow-up task for the team.",
    action: {
      action_type: "create_task",
      message: "Workflow executed",
      title: "Contact lead within 24 hours",
      assigned_to: "",
      recipient: "",
      subject: "Workflow notification",
      body_template: "Workflow completed.",
      url: "https://example.com/webhook",
      method: "POST",
    },
  },
  {
    id: "template-email-alert",
    name: "Email Alert",
    description: "Send an email alert when the workflow runs.",
    action: {
      action_type: "send_email",
      message: "Workflow executed",
      title: "Follow up lead",
      assigned_to: "",
      recipient: "team@example.com",
      subject: "Workflow alert",
      body_template: "A workflow event was triggered. Review the latest run details.",
      url: "https://example.com/webhook",
      method: "POST",
    },
  },
  {
    id: "template-webhook-sync",
    name: "Webhook Sync",
    description: "POST workflow data to an external integration endpoint.",
    action: {
      action_type: "webhook",
      message: "Workflow executed",
      title: "Follow up lead",
      assigned_to: "",
      recipient: "",
      subject: "Workflow notification",
      body_template: "Workflow completed.",
      url: "https://example.com/hooks/workflows",
      method: "POST",
    },
  },
];

const WORKFLOW_TEMPLATE_LIBRARY: WorkflowTemplate[] = [
  {
    id: "workflow-template-lead-intake",
    name: "Lead Intake Starter",
    description: "Log event, assign follow-up task, and notify team.",
    trigger_event_type: "lead_created",
    actions: [
      {
        action_type: "log",
        message: "Lead intake workflow started.",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "create_task",
        message: "Workflow executed",
        title: "Call lead and qualify requirements",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "send_email",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "sales@example.com",
        subject: "New lead ready for outreach",
        body_template: "A new lead is ready for sales outreach.",
        url: "https://example.com/webhook",
        method: "POST",
      },
    ],
  },
  {
    id: "workflow-template-task-completion-review",
    name: "Task Completion Review",
    description: "Log completion, notify ops, and queue QA follow-up.",
    trigger_event_type: "task_completed",
    actions: [
      {
        action_type: "log",
        message: "Task completion workflow triggered.",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "send_email",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "operations@example.com",
        subject: "Task completed - review required",
        body_template:
          "A task was completed. Please review the run details for verification.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "create_task",
        message: "Workflow executed",
        title: "Verify completed task output",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
    ],
  },
  {
    id: "workflow-template-lead-status-sync",
    name: "Lead Status Sync",
    description: "Push status updates to external systems and log changes.",
    trigger_event_type: "lead_status_changed",
    actions: [
      {
        action_type: "webhook",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/hooks/leads/status",
        method: "POST",
      },
      {
        action_type: "send_email",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "sales-manager@example.com",
        subject: "Lead status changed",
        body_template: "A lead status changed and was synced to external systems.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "log",
        message: "Lead status sync completed.",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
    ],
  },
  {
    id: "workflow-template-custom-monitoring",
    name: "Custom Event Monitoring",
    description: "Handle custom integration events with alert + webhook routing.",
    trigger_event_type: "custom",
    actions: [
      {
        action_type: "log",
        message: "Custom event received.",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/webhook",
        method: "POST",
      },
      {
        action_type: "webhook",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "",
        subject: "Workflow notification",
        body_template: "Workflow completed.",
        url: "https://example.com/hooks/custom-events",
        method: "POST",
      },
      {
        action_type: "send_email",
        message: "Workflow executed",
        title: "Follow up lead",
        assigned_to: "",
        recipient: "alerts@example.com",
        subject: "Custom workflow event processed",
        body_template:
          "A custom event was processed and routed via webhook. Check workflow logs.",
        url: "https://example.com/webhook",
        method: "POST",
      },
    ],
  },
];

function createId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `action-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createAction(
  actionType: WorkflowActionType = "log",
  overrides: Partial<Omit<ActionFormState, "id">> = {},
): ActionFormState {
  return {
    id: createId(),
    action_type: actionType,
    message: "Workflow executed",
    title: "Follow up lead",
    assigned_to: "",
    recipient: "",
    subject: "Workflow notification",
    body_template: "Workflow completed.",
    url: "https://example.com/webhook",
    method: "POST",
    ...overrides,
  };
}

function buildActionInput(action: ActionFormState, order: number): WorkflowActionInput {
  if (action.action_type === "log") {
    return {
      action_type: action.action_type,
      order,
      parameters: {
        message: action.message.trim(),
      },
    };
  }

  if (action.action_type === "create_task") {
    return {
      action_type: action.action_type,
      order,
      parameters: {
        title: action.title.trim(),
        ...(action.assigned_to.trim() ? { assigned_to: action.assigned_to.trim() } : {}),
      },
    };
  }

  if (action.action_type === "send_email") {
    return {
      action_type: action.action_type,
      order,
      parameters: {
        recipient: action.recipient.trim(),
        subject: action.subject.trim(),
        body_template: action.body_template.trim(),
      },
    };
  }

  return {
    action_type: action.action_type,
    order,
    parameters: {
      url: action.url.trim(),
      method: action.method,
    },
  };
}

function validateAction(action: ActionFormState, index: number): string | null {
  if (action.action_type === "log" && action.message.trim().length === 0) {
    return `Action ${index + 1}: log message is required.`;
  }

  if (action.action_type === "create_task" && action.title.trim().length === 0) {
    return `Action ${index + 1}: task title is required.`;
  }

  if (action.action_type === "send_email") {
    if (action.recipient.trim().length === 0) {
      return `Action ${index + 1}: recipient is required.`;
    }
    if (action.subject.trim().length === 0) {
      return `Action ${index + 1}: subject is required.`;
    }
    if (action.body_template.trim().length === 0) {
      return `Action ${index + 1}: body template is required.`;
    }
  }

  if (action.action_type === "webhook") {
    if (action.url.trim().length === 0) {
      return `Action ${index + 1}: webhook URL is required.`;
    }
    try {
      // Validate URL format early to avoid noisy backend errors.
      new URL(action.url.trim());
    } catch {
      return `Action ${index + 1}: webhook URL must be valid.`;
    }
  }

  return null;
}

function moveArrayItem<T>(items: T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function actionSummary(action: ActionFormState): string {
  if (action.action_type === "log") {
    return action.message.trim() || "No message";
  }
  if (action.action_type === "create_task") {
    return action.title.trim() || "No task title";
  }
  if (action.action_type === "send_email") {
    return `${action.recipient.trim() || "No recipient"} | ${action.subject.trim() || "No subject"}`;
  }
  return `${action.method} ${action.url.trim() || "No URL"}`;
}

export default function NewWorkflowPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerEventType, setTriggerEventType] = useState<string>("lead_created");
  const [enabled, setEnabled] = useState(true);
  const [workflowOrderInput, setWorkflowOrderInput] = useState("0");
  const [actions, setActions] = useState<ActionFormState[]>(() => [createAction("log")]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

  const trimmedName = useMemo(() => name.trim(), [name]);
  const triggerMeta = useMemo(
    () => TRIGGER_OPTIONS.find((option) => option.value === triggerEventType) ?? null,
    [triggerEventType],
  );

  const parsedOrder = useMemo(() => Number(workflowOrderInput), [workflowOrderInput]);

  const generatedDefinition = useMemo<WorkflowDefinitionInput>(
    () => ({
      trigger_event_type: triggerEventType,
      enabled,
      order: Number.isInteger(parsedOrder) && parsedOrder >= 0 ? parsedOrder : 0,
      actions: actions.map((action, index) => buildActionInput(action, index)),
    }),
    [actions, enabled, parsedOrder, triggerEventType],
  );

  const generatedJson = useMemo(
    () => JSON.stringify(generatedDefinition, null, 2),
    [generatedDefinition],
  );

  function updateAction(id: string, patch: Partial<ActionFormState>) {
    setActions((current) =>
      current.map((action) => (action.id === id ? { ...action, ...patch } : action)),
    );
  }

  function addAction(actionType: WorkflowActionType = "log") {
    setActions((current) => [...current, createAction(actionType)]);
  }

  function applyActionTemplate(templateId: string) {
    const template = ACTION_TEMPLATE_LIBRARY.find((item) => item.id === templateId);
    if (!template) {
      return;
    }
    setActions((current) => [
      ...current,
      createAction(template.action.action_type, template.action),
    ]);
    setCopyMessage(null);
  }

  function applyWorkflowTemplate(templateId: string) {
    const template = WORKFLOW_TEMPLATE_LIBRARY.find((item) => item.id === templateId);
    if (!template) {
      return;
    }
    setTriggerEventType(template.trigger_event_type);
    setActions(template.actions.map((action) => createAction(action.action_type, action)));
    setCopyMessage(null);
    setError(null);
  }

  function removeAction(id: string) {
    setActions((current) => {
      if (current.length === 1) {
        return current;
      }
      return current.filter((action) => action.id !== id);
    });
  }

  function moveActionUp(index: number) {
    if (index === 0) {
      return;
    }
    setActions((current) => moveArrayItem(current, index, index - 1));
  }

  function moveActionDown(index: number) {
    if (index >= actions.length - 1) {
      return;
    }
    setActions((current) => moveArrayItem(current, index, index + 1));
  }

  function resetBuilder() {
    setName("");
    setDescription("");
    setTriggerEventType("lead_created");
    setEnabled(true);
    setWorkflowOrderInput("0");
    setActions([createAction("log")]);
    setError(null);
    setCopyMessage(null);
  }

  async function copyPreview() {
    try {
      await navigator.clipboard.writeText(generatedJson);
      setCopyMessage("JSON copied.");
    } catch {
      setCopyMessage("Unable to copy JSON.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCopyMessage(null);

    if (!trimmedName) {
      setError("Name is required.");
      return;
    }

    if (!Number.isInteger(parsedOrder) || parsedOrder < 0) {
      setError("Workflow order must be a non-negative integer.");
      return;
    }

    if (actions.length === 0) {
      setError("At least one action is required.");
      return;
    }

    for (let i = 0; i < actions.length; i += 1) {
      const message = validateAction(actions[i], i);
      if (message) {
        setError(message);
        return;
      }
    }

    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setIsSubmitting(true);

    try {
      const created = await apiRequest<Workflow>("/api/v1/workflows", {
        method: "POST",
        authToken: token,
        body: {
          name: trimmedName,
          description: description.trim() || null,
          trigger_event_type: generatedDefinition.trigger_event_type,
          enabled: generatedDefinition.enabled,
          order: generatedDefinition.order,
          actions: generatedDefinition.actions,
        },
      });

      router.push(`/workflows/${created.id}`);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to create workflow.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Create Workflow</h1>
        <Link
          href="/workflows"
          className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
        >
          Back to Workflows
        </Link>
      </div>

      <form
        className="space-y-4 rounded-lg border border-border bg-surface p-5"
        onSubmit={handleSubmit}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm font-medium text-[#aaa]" htmlFor="name">
              Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
              placeholder="Lead Follow-Up Workflow"
            />
          </div>

          <div className="md:col-span-2">
            <label
              className="mb-1 block text-sm font-medium text-[#aaa]"
              htmlFor="description"
            >
              Description
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
              placeholder="Optional description for this workflow"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-[#aaa]"
              htmlFor="trigger-event-type"
            >
              Trigger Event
            </label>
            <select
              id="trigger-event-type"
              value={triggerEventType}
              onChange={(event) => setTriggerEventType(event.target.value)}
              className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
            >
              {TRIGGER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">
              {triggerMeta?.description ?? "Choose the event that starts this workflow."}
            </p>
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-[#aaa]"
              htmlFor="workflow-order"
            >
              Workflow Order
            </label>
            <input
              id="workflow-order"
              type="number"
              min={0}
              step={1}
              value={workflowOrderInput}
              onChange={(event) => setWorkflowOrderInput(event.target.value)}
              className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
            />
            <label className="mt-2 inline-flex items-center gap-2 text-sm text-[#aaa]">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(event) => setEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border text-brand focus:ring-brand/20"
              />
              Workflow is enabled
            </label>
          </div>
        </div>

        <div className="space-y-3 rounded-md border border-border p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[#aaa]">
                Actions
              </h2>
              <p className="text-xs text-muted">
                Add actions in sequence. Execution order follows this list.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {ACTION_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => addAction(option.value)}
                  className="rounded-md border border-border px-3 py-1 text-xs font-medium text-[#aaa] hover:bg-white/5"
                >
                  Add {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-dashed border-border bg-[#1a1a1a] p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#aaa]">
              Workflow Templates
            </p>
            <p className="mt-1 text-xs text-muted">
              Apply a starter workflow preset, then customize fields below.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {WORKFLOW_TEMPLATE_LIBRARY.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => applyWorkflowTemplate(template.id)}
                  className="rounded-md border border-border bg-[#141414] px-3 py-1 text-xs font-medium text-[#aaa] hover:bg-white/5"
                  title={template.description}
                >
                  Use {template.name}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-dashed border-border bg-[#1a1a1a] p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#aaa]">
              Action Templates
            </p>
            <p className="mt-1 text-xs text-muted">
              Insert pre-built action configurations.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {ACTION_TEMPLATE_LIBRARY.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => applyActionTemplate(template.id)}
                  className="rounded-md border border-border bg-[#141414] px-3 py-2 text-left hover:bg-white/5"
                >
                  <p className="text-xs font-semibold text-[#ccc]">{template.name}</p>
                  <p className="mt-1 text-xs text-muted">{template.description}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            {actions.map((action, index) => {
              const actionMeta =
                ACTION_OPTIONS.find((option) => option.value === action.action_type) ?? null;

              return (
                <article key={action.id} className="rounded-md border border-border bg-[#1a1a1a] p-3">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        Action {index + 1}: {actionMeta?.label ?? action.action_type}
                      </p>
                      <p className="text-xs text-muted">
                        {actionMeta?.description ?? "Configure this action."}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => moveActionUp(index)}
                        disabled={index === 0}
                        className="rounded-md border border-border px-2 py-1 text-xs text-[#aaa] hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        onClick={() => moveActionDown(index)}
                        disabled={index === actions.length - 1}
                        className="rounded-md border border-border px-2 py-1 text-xs text-[#aaa] hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        onClick={() => removeAction(action.id)}
                        disabled={actions.length === 1}
                        className="rounded-md border border-red-800/40 px-2 py-1 text-xs text-red-400 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                        Action Type
                      </label>
                      <select
                        value={action.action_type}
                        onChange={(event) =>
                          updateAction(action.id, {
                            action_type: event.target.value as WorkflowActionType,
                          })
                        }
                        className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                      >
                        {ACTION_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {action.action_type === "log" ? (
                      <div className="md:col-span-2">
                        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                          Message
                        </label>
                        <input
                          type="text"
                          value={action.message}
                          onChange={(event) =>
                            updateAction(action.id, { message: event.target.value })
                          }
                          className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                          placeholder="Workflow executed"
                        />
                      </div>
                    ) : null}

                    {action.action_type === "create_task" ? (
                      <>
                        <div className="md:col-span-2">
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Title
                          </label>
                          <input
                            type="text"
                            value={action.title}
                            onChange={(event) =>
                              updateAction(action.id, { title: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="Follow up lead"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Assigned To (optional UUID)
                          </label>
                          <input
                            type="text"
                            value={action.assigned_to}
                            onChange={(event) =>
                              updateAction(action.id, { assigned_to: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="User ID"
                          />
                        </div>
                      </>
                    ) : null}

                    {action.action_type === "send_email" ? (
                      <>
                        <div>
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Recipient
                          </label>
                          <input
                            type="email"
                            value={action.recipient}
                            onChange={(event) =>
                              updateAction(action.id, { recipient: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="name@example.com"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Subject
                          </label>
                          <input
                            type="text"
                            value={action.subject}
                            onChange={(event) =>
                              updateAction(action.id, { subject: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="Workflow notification"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Body Template
                          </label>
                          <textarea
                            rows={3}
                            value={action.body_template}
                            onChange={(event) =>
                              updateAction(action.id, { body_template: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="Notification body"
                          />
                        </div>
                      </>
                    ) : null}

                    {action.action_type === "webhook" ? (
                      <>
                        <div className="md:col-span-2">
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            URL
                          </label>
                          <input
                            type="url"
                            value={action.url}
                            onChange={(event) =>
                              updateAction(action.id, { url: event.target.value })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                            placeholder="https://example.com/webhook"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-[#aaa]">
                            Method
                          </label>
                          <select
                            value={action.method}
                            onChange={(event) =>
                              updateAction(action.id, {
                                method: event.target.value as WebhookMethod,
                              })
                            }
                            className="w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                          >
                            <option value="POST">POST</option>
                            <option value="GET">GET</option>
                            <option value="PUT">PUT</option>
                            <option value="PATCH">PATCH</option>
                            <option value="DELETE">DELETE</option>
                          </select>
                        </div>
                      </>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <div className="rounded-md border border-border p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[#aaa]">
            Visual Preview
          </h2>
          <p className="mt-1 text-xs text-muted">
            Quick view of trigger and action flow order.
          </p>
          <ol className="mt-3 space-y-2">
            <li className="rounded-md border border-border bg-[#1a1a1a] px-3 py-2 text-sm text-[#ccc]">
              Trigger:{" "}
              <span className="font-semibold">
                {triggerMeta?.label ?? triggerEventType}
              </span>
            </li>
            {actions.map((action, index) => {
              const actionMeta =
                ACTION_OPTIONS.find((option) => option.value === action.action_type) ?? null;
              return (
                <li
                  key={`${action.id}-preview`}
                  className="rounded-md border border-border bg-[#141414] px-3 py-2 text-sm text-[#ccc]"
                >
                  Step {index + 1}:{" "}
                  <span className="font-semibold">
                    {actionMeta?.label ?? action.action_type}
                  </span>
                  <p className="mt-1 text-xs text-muted">{actionSummary(action)}</p>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="rounded-md border border-border p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[#aaa]">
              JSON Preview
            </h2>
            <button
              type="button"
              onClick={() => void copyPreview()}
              className="rounded-md border border-border px-3 py-1 text-xs font-medium text-[#aaa] hover:bg-white/5"
            >
              Copy JSON
            </button>
          </div>
          <p className="mb-2 text-xs text-muted">
            Read-only preview for advanced users and debugging.
          </p>
          <pre className="max-h-72 overflow-auto rounded-md border border-border bg-slate-900 p-3 text-xs text-slate-100">
            <code>{generatedJson}</code>
          </pre>
          {copyMessage ? <p className="mt-2 text-xs text-[#aaa]">{copyMessage}</p> : null}
        </div>

        {error ? (
          <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Creating..." : "Create"}
          </button>
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
            onClick={resetBuilder}
          >
            Reset Builder
          </button>
        </div>
      </form>
    </section>
  );
}
