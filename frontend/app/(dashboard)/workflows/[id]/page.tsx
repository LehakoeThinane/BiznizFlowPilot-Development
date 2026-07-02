"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import { getStoredToken, logout } from "@/lib/auth";
import type { Workflow, WorkflowDefinitionInput } from "@/types/api";

interface WorkflowDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function buildDefinitionFromWorkflow(workflow: Workflow): WorkflowDefinitionInput {
  return {
    trigger_event_type: workflow.trigger_event_type,
    enabled: workflow.enabled,
    order: workflow.order,
    actions: workflow.actions
      .slice()
      .sort((a, b) => a.order - b.order)
      .map((action) => ({
        action_type: action.action_type,
        parameters: action.parameters,
        order: action.order,
      })),
  };
}

function parseDefinition(input: string): WorkflowDefinitionInput {
  let parsed: unknown;
  try {
    parsed = JSON.parse(input);
  } catch {
    throw new Error("Definition must be valid JSON.");
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Definition must be a JSON object.");
  }

  const record = parsed as Record<string, unknown>;

  if (
    typeof record.trigger_event_type !== "string" ||
    record.trigger_event_type.trim().length === 0
  ) {
    throw new Error("Definition requires a non-empty trigger_event_type.");
  }

  if (typeof record.enabled !== "boolean") {
    throw new Error("Definition requires a boolean enabled field.");
  }

  if (!Number.isInteger(record.order) || Number(record.order) < 0) {
    throw new Error("Definition requires a non-negative integer order.");
  }

  if (!Array.isArray(record.actions) || record.actions.length === 0) {
    throw new Error("Definition requires an actions array with at least one action.");
  }

  const actions = record.actions.map((action, index) => {
    if (!action || typeof action !== "object") {
      throw new Error(`Action at index ${index} must be an object.`);
    }

    const actionRecord = action as Record<string, unknown>;

    if (
      typeof actionRecord.action_type !== "string" ||
      actionRecord.action_type.trim().length === 0
    ) {
      throw new Error(`Action at index ${index} requires action_type.`);
    }

    if (!Number.isInteger(actionRecord.order) || Number(actionRecord.order) < 0) {
      throw new Error(`Action at index ${index} requires a non-negative integer order.`);
    }

    if (
      actionRecord.parameters === null ||
      actionRecord.parameters === undefined ||
      typeof actionRecord.parameters !== "object"
    ) {
      throw new Error(`Action at index ${index} requires parameters object.`);
    }

    return {
      action_type: actionRecord.action_type,
      parameters: actionRecord.parameters as Record<string, unknown>,
      order: Number(actionRecord.order),
    };
  });

  const sortedOrders = actions
    .map((action) => action.order)
    .sort((a, b) => a - b);
  for (let i = 0; i < sortedOrders.length; i += 1) {
    if (sortedOrders[i] !== i) {
      throw new Error("Action order must be sequential starting at 0.");
    }
  }

  return {
    trigger_event_type: record.trigger_event_type,
    enabled: record.enabled,
    order: Number(record.order),
    actions,
  };
}

export default function WorkflowDetailPage({ params }: WorkflowDetailPageProps) {
  const { id: workflowId } = use(params);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [showJson, setShowJson] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [definitionText, setDefinitionText] = useState("");

  const loadWorkflow = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const response = await apiRequest<Workflow>(`/api/v1/workflows/${workflowId}`, {
        method: "GET",
        authToken: token,
      });
      setWorkflow(response);
      setName(response.name);
      setDescription(response.description ?? "");
      setDefinitionText(JSON.stringify(buildDefinitionFromWorkflow(response), null, 2));
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      if (requestError instanceof ApiError && requestError.status === 404) {
        setError("Workflow not found");
      } else {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load workflow details",
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadWorkflow();
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadWorkflow]);

  const readOnlyDefinitionJson = useMemo(() => {
    if (!workflow) {
      return "";
    }
    return JSON.stringify(buildDefinitionFromWorkflow(workflow), null, 2);
  }, [workflow]);

  function startEditing() {
    if (!workflow) {
      return;
    }
    setError(null);
    setIsEditing(true);
    setShowJson(false);
    setName(workflow.name);
    setDescription(workflow.description ?? "");
    setDefinitionText(JSON.stringify(buildDefinitionFromWorkflow(workflow), null, 2));
  }

  function cancelEditing() {
    if (workflow) {
      setName(workflow.name);
      setDescription(workflow.description ?? "");
      setDefinitionText(JSON.stringify(buildDefinitionFromWorkflow(workflow), null, 2));
    }
    setIsEditing(false);
    setShowJson(false);
    setError(null);
  }

  async function saveChanges() {
    const token = getStoredToken();
    if (!token) {
      logout();
      window.location.replace("/login");
      return;
    }

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Name is required.");
      return;
    }

    let definition: WorkflowDefinitionInput;
    try {
      definition = parseDefinition(definitionText);
    } catch (validationError) {
      setError(
        validationError instanceof Error
          ? validationError.message
          : "Invalid definition JSON.",
      );
      return;
    }

    setIsSaving(true);
    setError(null);

    const payload = {
      name: trimmedName,
      description: description.trim() || null,
      trigger_event_type: definition.trigger_event_type,
      enabled: definition.enabled,
      order: definition.order,
      actions: definition.actions,
    };

    try {
      try {
        await apiRequest<Workflow>(`/api/v1/workflows/${workflowId}`, {
          method: "PUT",
          authToken: token,
          body: payload,
        });
      } catch (putError) {
        if (putError instanceof ApiError && putError.status === 405) {
          await apiRequest<Workflow>(`/api/v1/workflows/${workflowId}`, {
            method: "PATCH",
            authToken: token,
            body: payload,
          });
        } else {
          throw putError;
        }
      }

      await loadWorkflow();
      setIsEditing(false);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        logout();
        window.location.replace("/login");
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Unable to save workflow.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-white">Workflow Details</h1>
        <Link
          href="/workflows"
          className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5"
        >
          Back to Workflows
        </Link>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted">
          Loading workflow details...
        </div>
      ) : error && !workflow ? (
        <div className="rounded-md border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          <p>{error}</p>
          <button
            type="button"
            onClick={() => void loadWorkflow()}
            className="mt-2 rounded-md border border-red-800/40 px-3 py-1 text-xs font-medium hover:bg-red-900/20"
          >
            Retry
          </button>
        </div>
      ) : workflow ? (
        <div className="space-y-4 rounded-lg border border-border bg-surface p-5">
          {error ? (
            <p className="rounded-md border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Name</p>
              {isEditing ? (
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                />
              ) : (
                <p className="mt-1 text-base font-semibold text-white">{workflow.name}</p>
              )}
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Status</p>
              <p className="mt-1 text-sm text-[#ccc]">
                {workflow.enabled ? "Active" : "Inactive"}
              </p>
            </div>
            <div className="md:col-span-2">
              <p className="text-xs uppercase tracking-wide text-muted">Description</p>
              {isEditing ? (
                <textarea
                  rows={3}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-[#0f0f0f] text-white px-3 py-2 text-sm outline-none ring-brand/20 focus:ring-2"
                />
              ) : (
                <p className="mt-1 text-sm text-[#ccc]">
                  {workflow.description?.trim() || "No description"}
                </p>
              )}
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Created</p>
              <p className="mt-1 text-sm text-[#ccc]">{formatDate(workflow.created_at)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Updated</p>
              <p className="mt-1 text-sm text-[#ccc]">{formatDate(workflow.updated_at)}</p>
            </div>
          </div>

          <div>
            {isEditing ? (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">
                  Workflow Definition JSON
                </p>
                <textarea
                  rows={14}
                  value={definitionText}
                  onChange={(event) => setDefinitionText(event.target.value)}
                  className="mt-2 w-full rounded-md border border-border bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100 outline-none ring-brand/20 focus:ring-2"
                />
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs uppercase tracking-wide text-muted">
                    Workflow Definition
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowJson((current) => !current)}
                    className="rounded-md border border-border px-3 py-1 text-xs font-medium text-[#aaa] hover:bg-white/5"
                  >
                    {showJson ? "Hide JSON" : "Show JSON"}
                  </button>
                </div>
                {showJson ? (
                  <pre className="overflow-x-auto rounded-md border border-border bg-slate-900 p-4 text-xs text-slate-100">
                    <code>{readOnlyDefinitionJson}</code>
                  </pre>
                ) : (
                  <p className="text-sm text-[#aaa]">
                    The workflow definition JSON is hidden by default.
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {isEditing ? (
              <>
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => void saveChanges()}
                  className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={cancelEditing}
                  className="rounded-md border border-border px-4 py-2 text-sm text-[#aaa] hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={startEditing}
                className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white"
              >
                Edit
              </button>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
