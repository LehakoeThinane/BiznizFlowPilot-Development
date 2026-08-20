"""Entry point: `python -m mcp_server.server`.

Launched by Claude Desktop/Code as a local stdio process (see .mcp.json).
Talks stdio MCP to Claude on one side, and authenticated HTTP to the BFP
backend's REST API (assumed already running - see scripts/start-backend.ps1)
on the other. Holds no direct DB/service imports - every tool call is
translated into an HTTP call, so it reuses 100% of the backend's own
validation, business_id scoping, and role/feature-tier gating for free.

Startup order matters and is deliberately fail-loud at every step: a
misconfigured or unsafe server should print a clear error and exit non-zero
rather than run with fewer guarantees than the plan promises.

IMPORTANT: nothing in this module (or anything it imports) may print() to
stdout - stdout is the MCP protocol channel to Claude. All diagnostics go
through the `logging` module, configured below to write to stderr only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

import httpx
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcp_server import router_policy, tool_registry
from mcp_server.auth import AuthError, TokenStore
from mcp_server.client import BFPClient, ToolError
from mcp_server.config import MCPSettings, load_settings
from mcp_server.idempotency import IdempotencyCache
from mcp_server.tool_registry import Registries, ToolEntry

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mcp_server")

SEARCH_TOOL_NAME = "search_bfp_tools"
CALL_TOOL_NAME = "call_bfp_tool"
CALL_DESTRUCTIVE_TOOL_NAME = "call_bfp_destructive_tool"


class CircuitBreaker:
    """Session-level cap on severe/destructive-tier calls.

    Per-call approval protects against one bad call, not a sequence of many
    small ones - approval fatigue after the fortieth "approve?" click, or a
    prompt-injection chain that gets a human rubber-stamping a string of
    individually-plausible actions that add up to something bad
    collectively. Once tripped, every further severe/destructive call is
    refused for the rest of this process's life - restarting the MCP
    connection (a real, out-of-band action the human has to notice and take)
    is the only way to reset it, which is the point: it forces a deliberate
    re-engagement, not just "click approve" on the next prompt too.
    """

    def __init__(self, max_calls: int):
        self._max_calls = max_calls
        self._count = 0

    def check(self) -> None:
        if self._count >= self._max_calls:
            raise ToolError(
                429,
                f"Circuit breaker tripped: {self._max_calls} severe/destructive actions already executed in this "
                "session. Refusing further ones. Restart the MCP server connection (not just this conversation) "
                "to reset.",
            )

    def record(self) -> None:
        self._count += 1


def _fetch_openapi_spec(base_url: str, access_token: str) -> dict:
    resp = httpx.get(f"{base_url.rstrip('/')}/openapi.json", headers={"Authorization": f"Bearer {access_token}"}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def _to_mcp_tool(entry: ToolEntry) -> types.Tool:
    return types.Tool(
        name=entry.name,
        description=entry.description,
        inputSchema=entry.input_schema,
        annotations=types.ToolAnnotations(**entry.annotations),
    )


def _execute_entry(
    entry: ToolEntry, args: dict, client: BFPClient, idempotency: IdempotencyCache, page_size_cap: int
) -> object:
    args = dict(args)  # don't mutate the caller's dict

    resolved_path = entry.path
    for pname in entry.path_params:
        if pname not in args:
            raise ToolError(400, f"Missing required path parameter '{pname}'")
        resolved_path = resolved_path.replace(f"{{{pname}}}", str(args.pop(pname)))

    query = {k: args[k] for k in entry.query_params if k in args}
    if entry.is_list_operation and "limit" in query:
        try:
            query["limit"] = min(int(query["limit"]), page_size_cap)
        except (TypeError, ValueError):
            query["limit"] = page_size_cap
    elif entry.is_list_operation:
        query["limit"] = page_size_cap

    body = {k: args[k] for k in entry.body_properties if k in args} or None
    if entry.force_field_values:
        # Enforced here, not just documented in the schema/description -
        # e.g. workflow creation always lands disabled regardless of what
        # the model requests. See router_policy.py's Tier.SEVERE docstring.
        body = {**(body or {}), **entry.force_field_values}
        logger.info("Forcing %s on %s %s regardless of requested value", entry.force_field_values, entry.method, entry.path)

    if idempotency.is_deduped(entry.method, entry.path):
        cached = idempotency.get(entry.method, entry.path, {"query": query, "body": body})
        if cached is not None:
            logger.info("Idempotency hit for %s %s - returning cached result", entry.method, entry.path)
            return cached

    result = client.request(entry.method, resolved_path, params=query, json_body=body)

    if idempotency.is_deduped(entry.method, entry.path):
        idempotency.put(entry.method, entry.path, {"query": query, "body": body}, result)

    # Backstop truncation: the query-param cap above is the primary
    # defense, but if a list endpoint doesn't expose a "limit" param at all,
    # this still prevents an unbounded response from blowing the
    # conversation's context.
    if entry.is_list_operation and isinstance(result, list) and len(result) > page_size_cap:
        return {"items": result[:page_size_cap], "truncated": True, "returned": page_size_cap}

    return result


def _search_tools(registry: dict[str, ToolEntry], call_via: str, query: str, limit: int = 15) -> list[dict]:
    tokens = [t for t in query.lower().split() if t]
    scored: list[tuple[int, str]] = []
    for name, entry in registry.items():
        haystack = f"{name} {entry.description}".lower()
        score = sum(1 for t in tokens if t in haystack)
        if score > 0 or not tokens:
            scored.append((score, name))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [
        {
            "name": name,
            "description": registry[name].description,
            "inputSchema": registry[name].input_schema,
            "call_via": call_via,
        }
        for _score, name in scored[:limit]
    ]


async def run() -> None:
    try:
        settings: MCPSettings = load_settings()
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)

    tokens = TokenStore(settings)
    try:
        access_token = tokens.get_valid_access_token()
    except AuthError as exc:
        logger.error(str(exc))
        sys.exit(1)
    logger.info("Logged in to BFP backend at %s", settings.base_url)

    try:
        spec = _fetch_openapi_spec(settings.base_url, access_token)
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch OpenAPI schema from %s/openapi.json: %s", settings.base_url, exc)
        sys.exit(1)

    policy_problems = router_policy.validate_against_openapi(spec)
    if policy_problems:
        logger.error(
            "router_policy.py is incomplete relative to the live schema - refusing to start "
            "(this is the sole enforcement point for finance/hr/payroll/billing exclusion, "
            "given the account is role 'manager'):"
        )
        for p in policy_problems:
            logger.error("  - %s", p)
        sys.exit(1)

    registries: Registries = tool_registry.build_registries(spec, list_tool_page_size=settings.list_tool_page_size)

    self_check_problems = tool_registry.self_check(registries)
    if self_check_problems:
        logger.error("Split-registry self-check failed - refusing to start:")
        for p in self_check_problems:
            logger.error("  - %s", p)
        sys.exit(1)

    logger.info(
        "Registered %d severe standalone tool(s), %d destructive-dispatcher operation(s) (behind %s), and "
        "%d ordinary operation(s) (behind %s/%s)",
        len(registries.severe),
        len(registries.destructive),
        CALL_DESTRUCTIVE_TOOL_NAME,
        len(registries.dispatch),
        SEARCH_TOOL_NAME,
        CALL_TOOL_NAME,
    )

    client = BFPClient(settings.base_url, tokens)
    idempotency = IdempotencyCache(settings.idempotency_window_seconds)
    breaker = CircuitBreaker(settings.max_destructive_calls_per_session)

    server = Server("biznizflowpilot")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        tools = [_to_mcp_tool(entry) for entry in registries.severe.values()]
        tools.append(
            types.Tool(
                name=SEARCH_TOOL_NAME,
                description=(
                    "Search BFP's ordinary (non-destructive, non-external, non-standing-access) operations by "
                    "keyword, AND destructive/external ones (deletes, sends, etc.) - results indicate which "
                    "dispatcher (call_bfp_tool or call_bfp_destructive_tool) to use for each. Standing-access "
                    "grants (create a workflow, invite a user, etc.) are NOT found here - they're separate, "
                    "individually-named top-level tools you'll see directly in your tool list."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Keywords, e.g. 'list leads' or 'delete task'"}},
                    "required": ["query"],
                },
                annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False),
            )
        )
        tools.append(
            types.Tool(
                name=CALL_TOOL_NAME,
                description="Call an ordinary (non-destructive, non-external) BFP operation found via search_bfp_tools.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Exact name returned by search_bfp_tools"},
                        "args": {"type": "object", "description": "Arguments matching that tool's inputSchema"},
                    },
                    "required": ["tool_name"],
                },
                # Truthful only because registries.dispatch is guaranteed (by
                # self_check() above) to contain no destructive/severe ops.
                annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False),
            )
        )
        tools.append(
            types.Tool(
                name=CALL_DESTRUCTIVE_TOOL_NAME,
                description=(
                    "Call a destructive or external-facing BFP operation (delete, send email, etc.) found via "
                    "search_bfp_tools. Every call through this tool is destructive or external by construction."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Exact name returned by search_bfp_tools"},
                        "args": {"type": "object", "description": "Arguments matching that tool's inputSchema"},
                    },
                    "required": ["tool_name"],
                },
                # Truthful in the other direction: registries.destructive is
                # guaranteed (by self_check()) to contain ONLY destructive/
                # external ops, so destructiveHint: true never over-warns on
                # a read either.
                annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True),
            )
        )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == SEARCH_TOOL_NAME:
                q = arguments.get("query", "")
                results = _search_tools(registries.dispatch, CALL_TOOL_NAME, q) + _search_tools(
                    registries.destructive, CALL_DESTRUCTIVE_TOOL_NAME, q
                )
                return [types.TextContent(type="text", text=json.dumps(results, default=str))]

            if name == CALL_TOOL_NAME:
                target_name = arguments.get("tool_name")
                entry = registries.dispatch.get(target_name)
                if entry is None:
                    raise ToolError(
                        404,
                        f"Unknown tool_name '{target_name}' for call_bfp_tool - call search_bfp_tools first, or "
                        "it may be destructive/external (use call_bfp_destructive_tool instead)",
                    )
                result = _execute_entry(entry, arguments.get("args") or {}, client, idempotency, settings.list_tool_page_size)
                return [types.TextContent(type="text", text=json.dumps(result, default=str))]

            if name == CALL_DESTRUCTIVE_TOOL_NAME:
                target_name = arguments.get("tool_name")
                entry = registries.destructive.get(target_name)
                if entry is None:
                    raise ToolError(404, f"Unknown tool_name '{target_name}' for call_bfp_destructive_tool - call search_bfp_tools first")
                breaker.check()
                result = _execute_entry(entry, arguments.get("args") or {}, client, idempotency, settings.list_tool_page_size)
                breaker.record()
                return [types.TextContent(type="text", text=json.dumps(result, default=str))]

            entry = registries.severe.get(name)
            if entry is None:
                raise ToolError(404, f"Unknown tool '{name}'")
            breaker.check()
            result = _execute_entry(entry, arguments, client, idempotency, settings.list_tool_page_size)
            breaker.record()
            return [types.TextContent(type="text", text=json.dumps(result, default=str))]

        except ToolError as exc:
            logger.warning("Tool call failed: %s", exc)
            return [types.TextContent(type="text", text=str(exc))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
