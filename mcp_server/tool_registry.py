"""Builds MCP tools from BFP's OpenAPI schema, split into three registries.

Split, not purely generic - and why: a single generic call_bfp_tool(name,
args) dispatcher would solve the tool-count problem (~40 routers x
list/get/create/update/delete easily produces 150+ candidate tools, well
past the ~50-80 range where model tool-selection accuracy measurably
degrades) but breaks a safety property this whole design relies on: MCP tool
annotations (readOnlyHint/destructiveHint/idempotentHint) are declared once
per registered tool at tools/list time - they can't vary per call based on
arguments.

Three tiers (see router_policy.Tier for the full rationale):

- ORDINARY -> DISPATCH_REGISTRY, reachable only via search_bfp_tools +
  call_bfp_tool (destructiveHint: false - truthful, enforced by self_check()).
- DESTRUCTIVE -> DESTRUCTIVE_REGISTRY, reachable only via
  call_bfp_destructive_tool (destructiveHint: true - also truthful, also
  enforced by self_check(), for the same reason in reverse: only
  destructive/external ops are ever routed there).
- SEVERE -> SEVERE_TOOLS, each registered as its own individually-named
  top-level MCP tool. Reserved for operations granting *standing* access or
  capability (create a workflow, invite a new user, create a public
  document-share link) rather than a one-time effect - these need to stand
  out in Claude's tool list on their own, not blend into a bulk-approval
  dispatcher after the fortieth routine "approve delete_task?" click.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mcp_server import router_policy
from mcp_server.router_policy import Tier

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")
# Query-parameter names this codebase actually uses for pagination
# (confirmed against app/api/customers.py et al - "skip"/"limit" is the
# consistent convention here, not "page"/"per_page").
_PAGE_SIZE_PARAM_NAMES = ("limit",)


@dataclass
class ToolEntry:
    name: str
    method: str
    path: str  # OpenAPI path template, e.g. /api/v1/customers/{customer_id}
    description: str
    input_schema: dict[str, Any]
    path_params: list[str]
    query_params: list[str]
    body_properties: list[str]
    is_list_operation: bool
    external_side_effect: bool
    force_standalone: bool
    tier: Tier
    body_encoding: str = "json"  # "json" or "form" (application/x-www-form-urlencoded)
    force_field_values: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, bool] = field(default_factory=dict)


@dataclass
class Registries:
    severe: dict[str, ToolEntry]
    destructive: dict[str, ToolEntry]
    dispatch: dict[str, ToolEntry]


def build_registries(openapi_spec: dict, *, list_tool_page_size: int) -> Registries:
    components = openapi_spec.get("components", {}).get("schemas", {})
    severe: dict[str, ToolEntry] = {}
    destructive: dict[str, ToolEntry] = {}
    dispatch: dict[str, ToolEntry] = {}
    seen_names: set[str] = set()

    for path, path_item in openapi_spec.get("paths", {}).items():
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if op is None:
                continue
            tags = op.get("tags", [])
            if not router_policy.is_operation_included(method, path, tags):
                continue

            entry = _build_tool_entry(method, path, op, components, list_tool_page_size)

            if entry.name in seen_names:
                # method+path is an OpenAPI-unique key, so this can only
                # happen if two distinct operations produced the same
                # sanitized name - fail loud rather than silently overwrite
                # one tool with another.
                raise RuntimeError(
                    f"Tool name collision on '{entry.name}' ({method.upper()} {path}) - "
                    "two operations produced the same generated name. Adjust _build_tool_name()."
                )
            seen_names.add(entry.name)

            {Tier.SEVERE: severe, Tier.DESTRUCTIVE: destructive, Tier.ORDINARY: dispatch}[entry.tier][entry.name] = entry

    return Registries(severe=severe, destructive=destructive, dispatch=dispatch)


def self_check(registries: Registries) -> list[str]:
    """Verify the split-registry safety invariants actually hold.

    Run at real server startup (see server.py), not just trusted by design:
    every severe/destructive tool must carry destructiveHint True, and the
    ordinary dispatch registry must contain zero severe/destructive
    operations - the property call_bfp_tool's own annotation depends on
    (and, symmetrically, the destructive dispatcher must contain zero severe
    operations - the property call_bfp_destructive_tool's annotation and the
    "severe items get their own distinct tool name" design both depend on).
    """
    problems: list[str] = []
    for name, entry in {**registries.severe, **registries.destructive}.items():
        if not entry.annotations.get("destructiveHint"):
            problems.append(f"tool '{name}' (tier={entry.tier.value}) is missing destructiveHint=true")
    for name, entry in registries.dispatch.items():
        if entry.tier != Tier.ORDINARY:
            problems.append(f"ordinary dispatch registry contains a non-ordinary operation '{name}' (tier={entry.tier.value})")
    for name, entry in registries.destructive.items():
        if entry.tier == Tier.SEVERE:
            problems.append(f"destructive dispatcher contains a SEVERE operation '{name}' - it must be its own standalone tool")
    return problems


def _build_tool_entry(method: str, path: str, op: dict, components: dict, list_tool_page_size: int) -> ToolEntry:
    tags = op.get("tags", [])
    _scope, policy = router_policy.resolve_operation(method, path, tags)
    tier = policy.effective_tier(method)

    name = _build_tool_name(method, path)
    summary = op.get("summary") or op.get("operationId") or name
    description = summary
    if tier == Tier.SEVERE:
        description = f"[STANDING ACCESS/CAPABILITY - not a one-time effect] {summary}"
        if policy.force_field_values:
            forced = ", ".join(f"{k}={v!r}" for k, v in policy.force_field_values.items())
            description += f" (always created/updated with {forced} regardless of what you pass - activate it in the BFP UI)"
    elif policy.external_side_effect:
        description = f"[external: this notifies/acts on a party outside BFP] {summary}"
    elif policy.force_standalone:
        description = f"[high-consequence] {summary}"

    path_params: list[str] = []
    query_params: list[str] = []
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in op.get("parameters", []):
        pname = param["name"]
        pschema = _resolve_schema(param.get("schema", {}), components)
        if param.get("in") == "path":
            path_params.append(pname)
            required.append(pname)
        elif param.get("in") == "query":
            query_params.append(pname)
            if param.get("required"):
                required.append(pname)
        else:
            continue
        properties[pname] = {**pschema, "description": pschema.get("description", f"{param.get('in')} parameter")}

    body_properties: list[str] = []
    skipped_file_fields: list[str] = []
    request_body_content = op.get("requestBody", {}).get("content", {})
    body_encoding = "json"
    body_schema = request_body_content.get("application/json", {}).get("schema")
    if body_schema is None and "multipart/form-data" in request_body_content:
        # Endpoints that accept file uploads (Upload Document, Send Email
        # Message's attachments, etc.) declare a multipart body instead of
        # JSON - a form-only field set (no files) still submits fine as
        # application/x-www-form-urlencoded, which FastAPI's Form(...)
        # parses identically to multipart. File-shaped fields themselves
        # are skipped below since there's no way to pass binary content
        # through JSON tool arguments here.
        body_schema = request_body_content["multipart/form-data"].get("schema")
        body_encoding = "form"
    if body_schema:
        resolved_body = _resolve_schema(body_schema, components)
        for prop_name, prop_schema in resolved_body.get("properties", {}).items():
            if prop_name in properties:
                continue  # a path/query param already claimed this name - keep that one
            if _is_file_field(prop_schema):
                skipped_file_fields.append(prop_name)
                continue
            body_properties.append(prop_name)
            properties[prop_name] = prop_schema
        required.extend(
            r for r in resolved_body.get("required", []) if r not in required and r not in skipped_file_fields
        )

    if skipped_file_fields:
        note = f" (NOTE: this operation also accepts file field(s) {skipped_file_fields} not supported through this interface)"
        description = description + note

    is_list_operation = method.upper() == "GET" and str(summary).lower().startswith("list ")
    if is_list_operation:
        _cap_page_size(properties, query_params, list_tool_page_size)

    input_schema = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = required

    annotations = {
        "readOnlyHint": method.upper() in ("GET", "HEAD"),
        "destructiveHint": tier in (Tier.DESTRUCTIVE, Tier.SEVERE),
        "idempotentHint": method.upper() in ("GET", "HEAD", "PUT", "DELETE"),
    }

    return ToolEntry(
        name=name,
        method=method.upper(),
        path=path,
        description=description,
        input_schema=input_schema,
        path_params=path_params,
        query_params=query_params,
        body_properties=body_properties,
        body_encoding=body_encoding,
        is_list_operation=is_list_operation,
        external_side_effect=policy.external_side_effect,
        force_standalone=policy.force_standalone,
        tier=tier,
        force_field_values=dict(policy.force_field_values),
        annotations=annotations,
    )


def _is_file_field(prop_schema: dict) -> bool:
    """Whether a resolved property schema represents a file/binary upload -
    these can't be passed through JSON-typed MCP tool arguments."""
    if prop_schema.get("format") == "binary" or "contentMediaType" in prop_schema:
        return True
    items = prop_schema.get("items")
    if isinstance(items, dict) and (items.get("format") == "binary" or "contentMediaType" in items):
        return True
    return False


def _cap_page_size(properties: dict, query_params: list[str], cap: int) -> None:
    """Hard-cap a list tool's page-size parameter at generation time.

    Rewrites the schema so the model sees `maximum: cap` (and defaults to
    it) - mcp_server/server.py's executor separately clamps whatever value
    actually arrives, so this isn't just advisory in the schema; a business
    with a few thousand rows can't blow the conversation's context through
    one list_* call, whether the model respects the schema hint or not.
    """
    for pname in _PAGE_SIZE_PARAM_NAMES:
        if pname in query_params and pname in properties:
            properties[pname] = {**properties[pname], "default": cap, "maximum": cap}


_PATH_PARAM_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _build_tool_name(method: str, path: str) -> str:
    """Collision-proof by construction: derived from the full method+path,
    which is already OpenAPI's unique key - not a coarser "tag + resource"
    heuristic that could collapse two distinct operations onto one name.
    """
    trimmed = path
    for prefix in ("/api/v1", "/platform/v1"):
        if trimmed.startswith(prefix):
            trimmed = trimmed[len(prefix):]
            break
    trimmed = _PATH_PARAM_RE.sub(lambda m: f"by_{m.group(1)}", trimmed)
    segments = [s for s in trimmed.replace("-", "_").split("/") if s]
    return "_".join([method.lower(), *segments]) if segments else method.lower()


def _resolve_schema(schema: dict, components: dict, _seen: frozenset[str] = frozenset()) -> dict:
    """Inline $ref schemas recursively using components/schemas as the store.

    Cycle-safe: a $ref encountered a second time within the same resolution
    chain (self-referencing schemas do exist in a large Pydantic model set)
    is left as an unresolved {"$ref": ...} rather than recursing forever.
    """
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in _seen:
            return {"$ref": ref}
        ref_name = ref.rsplit("/", 1)[-1]
        target = components.get(ref_name)
        if target is None:
            return schema
        return _resolve_schema(target, components, _seen | {ref})

    resolved = dict(schema)
    if "properties" in resolved:
        resolved["properties"] = {k: _resolve_schema(v, components, _seen) for k, v in resolved["properties"].items()}
    if "items" in resolved:
        resolved["items"] = _resolve_schema(resolved["items"], components, _seen)
    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator in resolved:
            resolved[combinator] = [_resolve_schema(s, components, _seen) for s in resolved[combinator]]
    return resolved
