"""Allow/deny policy for which BFP REST operations become MCP tools.

This is the enforcement point described in the MCP-server plan: the
dedicated service account is role `manager` (see docstring on
mcp_server/auth.py), which means there is *no* backend role check standing
between this file and finance/hr/payroll/billing data - `router_policy` is
the sole fence. Every operation in every allowed tag must be classified
explicitly (see `mcp_server/tests/test_router_policy.py`); there is no
silent default for `external_side_effect`.

Two levels of policy:

- `TAG_POLICY` - the default scope for every operation under an OpenAPI tag.
  `ALLOW_READ` lets GET/HEAD operations under that tag through and defers
  every mutating operation (no write tool is generated for it, whether or
  not it's separately overridden). `ALLOW_WRITE` lets both reads and writes
  through. `DENY` excludes the tag entirely.
- `OPERATION_OVERRIDES` - per (method, path) exceptions to the tag default,
  keyed on the exact OpenAPI path template. Used for two things:
    1. Carving a specific operation *out* of an otherwise-allowed tag (e.g.
       payroll-generation/payslip endpoints, which sit under the `hr` tag
       but are excluded even as reads - see below).
    2. Flagging `external_side_effect=True` (or `force_standalone=True` for
       a non-external but still high-consequence action like a password
       change) so `tool_registry.py` gives that operation its own
       standalone MCP tool with an accurate `destructiveHint`, instead of
       routing it through the generic, non-destructive `call_bfp_tool`
       dispatcher.

Tag/operation data below reflects the actual live OpenAPI schema (see
mcp_server/tests/fixtures/openapi_snapshot.json, produced by importing
app.main and calling app.openapi() - no live DB/server needed), not a
guess at what the routers "should" expose.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Scope(str, Enum):
    ALLOW_READ = "allow_read"
    ALLOW_WRITE = "allow_write"
    DENY = "deny"


# --------------------------------------------------------------------------
# Tag-level defaults. Every tag present in the live OpenAPI schema must
# appear here - mcp_server/tests/test_router_policy.py fails loudly on any
# tag it finds that isn't listed, so a newly added router can't silently
# start generating tools (or silently stay hidden) without a decision.
# --------------------------------------------------------------------------
TAG_POLICY: dict[str, Scope] = {
    # Untagged routes in app/main.py itself: /health plus the /me and
    # /users/me/* self-service endpoints. /health is denied per-operation
    # below (not a business action); the rest is the "users (self profile)"
    # write scope from the plan.
    "<no-tag>": Scope.ALLOW_WRITE,
    # Used internally by mcp_server/auth.py to obtain this server's own
    # bearer token - never exposed as a tool a model could call.
    "auth": Scope.DENY,
    # Real money movement via Stripe/PayFast; also has no auth at all by
    # design (see app/main.py), so excluding it is doubly correct.
    "billing": Scope.DENY,
    # BFP's own in-app AI co-pilot chat endpoint - no reason for this MCP
    # server to call BFP's AI feature on itself.
    "chat": Scope.DENY,
    "customers": Scope.ALLOW_WRITE,
    "dashboard": Scope.ALLOW_READ,
    "document-sharing": Scope.ALLOW_WRITE,
    "documents": Scope.ALLOW_WRITE,
    # Per-user connected-mailbox management (was called "user_email" in the
    # plan; the real OpenAPI tag is "email").
    "email": Scope.ALLOW_WRITE,
    "events": Scope.ALLOW_WRITE,
    # Financial statements - read only in v1, writes deferred pending
    # explicit opt-in (see plan). The ALLOW_READ tag policy alone already
    # excludes every POST/PATCH/DELETE under this tag - no per-operation
    # overrides needed for that.
    "finance": Scope.ALLOW_READ,
    "folders": Scope.ALLOW_WRITE,
    # Employee directory / leave - read only in v1, writes deferred, same as
    # finance. Payroll-generation and payslip endpoints live under this same
    # tag (not the separate "payroll" tag below) and are excluded entirely,
    # including as reads, via OPERATION_OVERRIDES - a payslip PDF is
    # sensitive personal financial data, not ordinary HR-directory reading.
    "hr": Scope.ALLOW_READ,
    "inventory": Scope.ALLOW_WRITE,
    "invites": Scope.ALLOW_WRITE,
    "invoices": Scope.ALLOW_WRITE,
    "leads": Scope.ALLOW_WRITE,
    # Public, no-auth lead-capture forms for marketing-site visitors - not
    # this authenticated business user's action to take.
    "marketing": Scope.DENY,
    # Separate CMS admin auth boundary (effective_marketing_cms_secret_key),
    # irrelevant to day-to-day BFP business use.
    "marketing-cms": Scope.DENY,
    "meetings": Scope.ALLOW_WRITE,
    "messaging": Scope.ALLOW_WRITE,
    "metrics": Scope.ALLOW_READ,
    "notifications": Scope.ALLOW_WRITE,
    "onboarding": Scope.ALLOW_WRITE,
    # Cross-subsidiary org structure - deferred, not yet reviewed for v1;
    # easy to add later by flipping this to ALLOW_READ/ALLOW_WRITE.
    "organization": Scope.DENY,
    # Pays employees; gated on PRIVILEGED_ROLES in app/api/payroll.py.
    # High blast radius, no upside to LLM-tool-call exposure - excluded
    # entirely, matching billing.py's treatment.
    "payroll": Scope.DENY,
    # Different JWT secret boundary entirely (effective_platform_secret_key)
    # - the tenant token this account holds couldn't authenticate against
    # these even if they were allow-listed.
    "platform-admin": Scope.DENY,
    "platform-auth": Scope.DENY,
    "products": Scope.ALLOW_WRITE,
    "purchase-orders": Scope.ALLOW_WRITE,
    "purchase-requisitions": Scope.ALLOW_WRITE,
    "sales-orders": Scope.ALLOW_WRITE,
    "search": Scope.ALLOW_READ,
    # Public, no-auth trial signup - not this authenticated user's action.
    "signup": Scope.DENY,
    "suppliers": Scope.ALLOW_WRITE,
    "tasks": Scope.ALLOW_WRITE,
    # Just the bare business-directory listing (GET /api/v1/users); the
    # self-profile mutating endpoints live under "<no-tag>" above.
    "users": Scope.ALLOW_READ,
    "workflow-definitions": Scope.ALLOW_WRITE,
    "workflows": Scope.ALLOW_WRITE,
}


class Tier(str, Enum):
    """Which of the three MCP-visible surfaces an operation ends up on.

    Introduced after review found the original binary
    standalone-vs-dispatcher split conflated two different risk shapes: a
    one-time external action (send this invoice, delete this task) and an
    operation that installs *standing, unsupervised, recurring* capability
    (create a workflow that keeps firing forever, grant a new person a
    permanent login). The latter deserves to stand out in Claude's tool list
    on its own, not be one more entry in a bulk-approval dispatcher.

    - ORDINARY: reads and routine internal writes. Reached only through
      search_bfp_tools + call_bfp_tool (annotated destructiveHint=false -
      truthful because nothing destructive/external/severe is ever routed
      through it, enforced by tool_registry.self_check()).
    - DESTRUCTIVE: single-instance, bounded-blast-radius destructive or
      external actions - an ordinary DELETE, or a one-time external_side_effect
      like emailing an invoice. Reached through call_bfp_destructive_tool,
      annotated destructiveHint=true uniformly (truthful for the same reason
      as above: only destructive/external ops ever land here).
    - SEVERE: registered as its own individually-named top-level MCP tool,
      not folded into a dispatcher - reserved for operations that grant
      *standing* access/capability rather than a one-time effect (create an
      invitation, create/update a workflow or workflow definition, create a
      public document-share link). Distinct top-level names make it harder
      for a model to reach one of these by construction/pattern-matching the
      way it could plausibly guess a call_bfp_destructive_tool argument.
    """

    ORDINARY = "ordinary"
    DESTRUCTIVE = "destructive"
    SEVERE = "severe"


@dataclass(frozen=True)
class OperationPolicy:
    """A per-(method, path) override of the tag-level default."""

    # None = inherit the tag's Scope; otherwise overrides it for this
    # specific operation only (used to carve payroll/payslip ops out of the
    # otherwise-read-allowed "hr" tag, to deny /health, and to remove
    # operations this account's role can never actually perform - see the
    # OWNER_ONLY entries below).
    scope_override: Scope | None
    # True if this operation's real-world effect reaches outside BFP's own
    # database in a way an ordinary CRUD write doesn't - sending an email,
    # granting external portal credentials, or calling a paid external API.
    # Implies at least Tier.DESTRUCTIVE (see effective_tier()).
    external_side_effect: bool = False
    # True for an operation that isn't "external" by the definition above
    # but is still high-consequence enough to deserve the same non-ordinary
    # treatment. Implied automatically when external_side_effect=True.
    force_standalone: bool = False
    # Explicit tier override. None means "derive from external_side_effect/
    # force_standalone/HTTP method" via effective_tier() - only set this to
    # force Tier.SEVERE (the DELETE/external_side_effect-implies-DESTRUCTIVE
    # default is usually right; SEVERE is reserved for standing-access grants,
    # see the Tier docstring).
    tier_override: Tier | None = None
    # Field(s) this operation's outgoing request body must always carry,
    # regardless of what the model requests - e.g. {"enabled": False} on
    # workflow creation, so an agent-created workflow can never activate
    # itself. Enforced in mcp_server/server.py's executor, not just documented.
    force_field_values: dict = None  # type: ignore[assignment]
    note: str = ""

    def __post_init__(self):
        if self.force_field_values is None:
            object.__setattr__(self, "force_field_values", {})

    def effective_tier(self, method: str) -> Tier:
        if self.tier_override is not None:
            return self.tier_override
        if method.upper() == "DELETE" or self.external_side_effect or self.force_standalone:
            return Tier.DESTRUCTIVE
        return Tier.ORDINARY


# --------------------------------------------------------------------------
# Per-operation overrides. Keyed on the exact OpenAPI path template (as it
# appears in openapi.json's "paths", e.g. "/api/v1/customers/{customer_id}"),
# not a resolved URL.
# --------------------------------------------------------------------------
OPERATION_OVERRIDES: dict[tuple[str, str], OperationPolicy] = {
    # --- <no-tag>: /health is an ops liveness probe, not a business action ---
    ("GET", "/health"): OperationPolicy(Scope.DENY, note="ops liveness probe, not a business action"),
    ("HEAD", "/health"): OperationPolicy(Scope.DENY, note="ops liveness probe, not a business action"),
    # Excluded entirely (not just flagged) after review: this tool set
    # ingests a lot of attacker-influenceable content (lead notes, inbound
    # emails, uploaded document text) as conversation context. A
    # password-change capability sitting behind that is a textbook
    # indirect-prompt-injection target ("helpfully" reset credentials on
    # hostile instructions embedded in a CRM field) - and unlike other
    # SEVERE-tier actions, there's no legitimate reason an AI agent needs to
    # change a human's password on their behalf at all. Removed rather than
    # merely flagged.
    ("POST", "/api/v1/users/me/change-password"): OperationPolicy(
        Scope.DENY, note="indirect-prompt-injection target; no legitimate agent use case - excluded entirely, not just flagged"
    ),

    # --- OWNER_ONLY deletes: app/services/{customer,task,lead,product,
    # supplier,inventory}.py each gate their delete() with
    # require_role(current_user, OWNER_ONLY, ...) - a stricter bar than the
    # PRIVILEGED_ROLES (owner+manager) used everywhere else these routers
    # gate writes. Confirmed by grep, not assumed: customer.py/task.py/
    # lead.py's docstrings literally say "RBAC: Only owner can permanently
    # delete." Since the account is role manager (required for invoice/
    # invite writes elsewhere - see mcp_server/auth.py), these six operations
    # would 403 every time regardless of router_policy - generated, approved
    # by the user, then rejected by the backend. Excluded entirely rather
    # than shipping a tool that can never succeed; escalating the account to
    # owner to make them work would defeat BFP's own deliberate design
    # decision that permanent deletion of this data needs the single most
    # privileged role, not just "a manager." Also resolves the "soft vs hard
    # delete" question for these specifically: all six are confirmed hard,
    # permanent deletes (session.delete()/repo hard-delete, no deleted_at
    # soft-delete column) - BFP's own author already treats them as the most
    # severe tier of destructive action, which is exactly why they're
    # owner-only in the first place.
    ("DELETE", "/api/v1/customers/{customer_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/customer.py) - would 403 for the manager-role account"
    ),
    ("DELETE", "/api/v1/tasks/{task_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/task.py) - would 403 for the manager-role account"
    ),
    ("DELETE", "/api/v1/leads/{lead_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/lead.py) - would 403 for the manager-role account"
    ),
    ("DELETE", "/api/v1/products/{product_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/product.py) - would 403 for the manager-role account"
    ),
    ("DELETE", "/api/v1/suppliers/{supplier_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/supplier.py) - would 403 for the manager-role account"
    ),
    ("DELETE", "/api/v1/inventory/locations/{location_id}"): OperationPolicy(
        Scope.DENY, note="OWNER_ONLY hard delete (app/services/inventory.py) - would 403 for the manager-role account"
    ),

    # --- hr: carve payroll-generation/payslip endpoints out entirely ---
    ("POST", "/api/v1/hr/payroll/generate"): OperationPolicy(Scope.DENY, note="payroll run - same sensitivity class as the excluded payroll tag"),
    ("GET", "/api/v1/hr/payroll"): OperationPolicy(Scope.DENY, note="payroll run data"),
    ("GET", "/api/v1/hr/payroll/{period_id}"): OperationPolicy(Scope.DENY, note="payroll run data"),
    ("PATCH", "/api/v1/hr/payroll/{period_id}/approve"): OperationPolicy(Scope.DENY, note="payroll run data"),
    ("PATCH", "/api/v1/hr/payroll/payslips/{payslip_id}"): OperationPolicy(Scope.DENY, note="individual payslip - sensitive personal financial data"),
    ("GET", "/api/v1/hr/payroll/payslips/{payslip_id}/pdf"): OperationPolicy(Scope.DENY, note="individual payslip PDF - sensitive personal financial data"),

    # --- meetings: confirmed via app/services/meeting.py to send real
    # external emails (send_meeting_invite_email / _update_email /
    # _cancelled_email) to any external_emails participants ---
    ("POST", "/api/v1/meetings"): OperationPolicy(
        None, external_side_effect=True, note="sends external meeting-invite emails (app/services/meeting.py)"
    ),
    ("PATCH", "/api/v1/meetings/{meeting_id}"): OperationPolicy(
        None, external_side_effect=True, note="sends external meeting update/cancellation emails"
    ),

    # --- invoices: emails the invoice to the customer ---
    ("POST", "/api/v1/invoices/{inv_id}/send-email"): OperationPolicy(
        None, external_side_effect=True, note="emails the invoice to the customer"
    ),

    # --- documents: emails the document to an external recipient ---
    ("POST", "/api/v1/documents/{document_id}/email"): OperationPolicy(
        None, external_side_effect=True, note="emails the document to an external recipient"
    ),

    # --- email: sends from the user's connected mailbox ---
    ("POST", "/api/v1/email-account/send"): OperationPolicy(
        None, external_side_effect=True, note="sends an email from the connected mailbox"
    ),

    # --- customers: grants an outside party (the customer) real login
    # credentials to the customer portal ---
    ("POST", "/api/v1/customers/{customer_id}/portal-access"): OperationPolicy(
        None, external_side_effect=True, note="grants the customer external login credentials to the customer portal"
    ),

    # --- leads: calls Google Places API - real external cost per call,
    # same "can't be undone by fixing a database row" property as an email
    # send, even though no external party is directly notified ---
    ("POST", "/api/v1/leads/find"): OperationPolicy(
        None, external_side_effect=True, note="calls the paid Google Places API per invocation"
    ),

    # --- workflows/workflow-definitions: SEVERE, not just DESTRUCTIVE.
    # Every other external_side_effect operation in this file is a one-time
    # action - a human approves it once, it happens once. Creating or
    # re-activating a workflow is different in kind: it installs a standing
    # instruction that keeps firing, unsupervised, until someone disables it.
    # If a workflow's configured action is an email/webhook step, approving
    # "create workflow" once is really approving an unbounded number of
    # future external actions the human will never see individual approval
    # prompts for. Mitigated two ways: (1) SEVERE tier - its own clearly
    # distinct standalone tool, not folded into a bulk dispatcher; (2)
    # force_field_values forces enabled/is_active=False on every create and
    # update, REGARDLESS of what the model requests - so this MCP server can
    # only ever produce a disabled draft. Turning it on requires a human
    # action in the actual BFP UI, a separate channel from the conversation
    # that requested it. See mcp_server/server.py's executor for the
    # enforcement, not just the schema.
    ("POST", "/api/v1/workflows"): OperationPolicy(
        None, tier_override=Tier.SEVERE, force_field_values={"enabled": False},
        note="installs a standing, recurring automation - always created disabled; enabling it requires the BFP UI"
    ),
    ("PATCH", "/api/v1/workflows/{workflow_id}"): OperationPolicy(
        None, tier_override=Tier.SEVERE, force_field_values={"enabled": False},
        note="could re-enable or change the actions of an existing standing automation - see POST /workflows above"
    ),
    # Toggle is the enable/disable action itself - excluded entirely rather
    # than allowed-but-forced-off, since "disable only" can't be expressed
    # without either lying in the schema or adding argument-dependent
    # behavior this design deliberately avoids elsewhere (see Tier docstring
    # / the split-registry rationale in tool_registry.py). Enabling or
    # disabling a workflow is a decision for a human in the BFP UI, not the
    # agent, full stop.
    ("PATCH", "/api/v1/workflows/{workflow_id}/toggle"): OperationPolicy(
        Scope.DENY, note="enable/disable must happen in the BFP UI, never via the agent - see POST /workflows above"
    ),
    ("POST", "/api/v1/workflow-definitions"): OperationPolicy(
        None, tier_override=Tier.SEVERE, force_field_values={"is_active": False},
        note="installs a standing, recurring automation - always created inactive; activating it requires the BFP UI"
    ),
    ("PATCH", "/api/v1/workflow-definitions/{definition_id}"): OperationPolicy(
        None, tier_override=Tier.SEVERE, force_field_values={"is_active": False},
        note="could re-activate or change the actions of an existing standing automation - see POST above"
    ),

    # --- invites: SEVERE, not just an ordinary write. Grants a brand-new
    # person a real login into the entire ERP - a standing capability grant,
    # not a one-time effect, and at least as consequential as customer
    # portal-access (already flagged) if not more so given the scope of
    # access an internal BFP account has versus a customer-portal account.
    ("POST", "/api/v1/users/invite"): OperationPolicy(
        None, tier_override=Tier.SEVERE, external_side_effect=True,
        note="grants a new person a standing login into the entire ERP, not a one-time effect"
    ),

    # --- document-sharing: SEVERE. Confirmed via app/main.py -
    # document_share.public_router is mounted with no auth required (same
    # treatment as billing/customer_portal/meeting_rsvp/website_chat) - so a
    # share link is a real, standing, unauthenticated access grant: anyone
    # with the URL can view the document until it's revoked. The revoke
    # operation is already an ordinary DELETE; it's creation that's the
    # actual exposure, and that was originally under-flagged.
    ("POST", "/api/v1/documents/{document_id}/share"): OperationPolicy(
        None, tier_override=Tier.SEVERE, external_side_effect=True,
        note="creates a standing, unauthenticated public access link (confirmed via app/main.py's public_router mount)"
    ),
}


# --------------------------------------------------------------------------
# Every other mutating operation in an included tag: reviewed against its
# router/service code (no send_*_email / notify-external-party / paid-API
# call found) and recorded here as an ordinary internal write with
# external_side_effect=False. This set exists so that a *new* mutating
# endpoint added later to an already-allowed router has to be explicitly
# added to either this set or OPERATION_OVERRIDES before it can generate a
# tool at all - see validate_against_openapi() below, which fails loudly on
# any included mutating operation present in neither.
# --------------------------------------------------------------------------
REVIEWED_ORDINARY_WRITES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/v1/customers"),
        ("PATCH", "/api/v1/customers/{customer_id}"),
        ("DELETE", "/api/v1/customers/{customer_id}/portal-access"),
        ("POST", "/api/v1/documents"),
        ("POST", "/api/v1/documents/compose"),
        ("PATCH", "/api/v1/documents/{document_id}/draft"),
        ("POST", "/api/v1/documents/{document_id}/finish"),
        ("POST", "/api/v1/documents/{document_id}/duplicate"),
        ("DELETE", "/api/v1/documents/{document_id}"),
        ("PATCH", "/api/v1/documents/{document_id}/restrict"),
        ("POST", "/api/v1/documents/{document_id}/access-requests"),
        ("POST", "/api/v1/documents/access-requests/{request_id}/approve"),
        ("POST", "/api/v1/documents/access-requests/{request_id}/deny"),
        ("POST", "/api/v1/documents/{document_id}/checkout"),
        ("POST", "/api/v1/documents/{document_id}/checkout/cancel"),
        ("POST", "/api/v1/documents/{document_id}/checkin"),
        ("POST", "/api/v1/folders"),
        ("PATCH", "/api/v1/folders/{folder_id}"),
        ("DELETE", "/api/v1/folders/{folder_id}"),
        ("DELETE", "/api/v1/documents/share/{link_id}"),
        ("POST", "/api/v1/events"),
        ("PATCH", "/api/v1/events/{event_id}"),
        ("POST", "/api/v1/leads"),
        ("POST", "/api/v1/leads/schedules"),
        ("PATCH", "/api/v1/leads/schedules/{schedule_id}"),
        ("DELETE", "/api/v1/leads/schedules/{schedule_id}"),
        ("PATCH", "/api/v1/leads/{lead_id}"),
        ("POST", "/api/v1/leads/{lead_id}/assign/{assigned_to}"),
        ("POST", "/api/v1/tasks"),
        ("PATCH", "/api/v1/tasks/{task_id}"),
        ("POST", "/api/v1/tasks/{task_id}/assign/{assigned_to}"),
        ("DELETE", "/api/v1/users/invites/{invite_id}"),
        ("POST", "/api/v1/meetings/{meeting_id}/respond"),
        ("POST", "/api/v1/meetings/{meeting_id}/start"),
        ("POST", "/api/v1/meetings/{meeting_id}/end"),
        ("POST", "/api/v1/meetings/{meeting_id}/join"),
        ("POST", "/api/v1/messaging/conversations"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/messages"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/read"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/attachments"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/contacts"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/events/share"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/events/schedule"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/stickers"),
        ("POST", "/api/v1/messaging/conversations/{conversation_id}/polls"),
        ("POST", "/api/v1/messaging/polls/{poll_id}/vote"),
        ("PUT", "/api/v1/email-account"),
        ("DELETE", "/api/v1/email-account"),
        ("PUT", "/api/v1/email-account/display-prefs"),
        ("DELETE", "/api/v1/email-account/messages/{uid}"),
        ("PATCH", "/api/v1/email-account/messages/{uid}/flags"),
        ("POST", "/api/v1/email-account/messages/{uid}/archive"),
        ("DELETE", "/api/v1/workflows/{workflow_id}"),
        ("DELETE", "/api/v1/workflow-definitions/{definition_id}"),
        ("POST", "/api/v1/onboarding/help"),
        ("POST", "/api/v1/products"),
        ("PATCH", "/api/v1/products/{product_id}"),
        ("POST", "/api/v1/suppliers"),
        ("PATCH", "/api/v1/suppliers/{supplier_id}"),
        ("POST", "/api/v1/inventory/locations"),
        ("PATCH", "/api/v1/inventory/locations/{location_id}"),
        ("POST", "/api/v1/inventory/stock/adjust"),
        ("POST", "/api/v1/sales-orders"),
        ("PATCH", "/api/v1/sales-orders/{order_id}"),
        ("POST", "/api/v1/purchase-orders"),
        ("PATCH", "/api/v1/purchase-orders/{po_id}"),
        ("POST", "/api/v1/purchase-requisitions"),
        ("PATCH", "/api/v1/purchase-requisitions/{pr_id}/status"),
        ("POST", "/api/v1/purchase-requisitions/{pr_id}/convert"),
        ("POST", "/api/v1/invoices"),
        ("DELETE", "/api/v1/invoices/{inv_id}"),
        ("PATCH", "/api/v1/invoices/{inv_id}/status"),
        ("PATCH", "/api/v1/notifications/{notif_id}/read"),
        ("PATCH", "/api/v1/notifications/read-all"),
        ("PATCH", "/api/v1/users/me"),
        ("PATCH", "/api/v1/users/me/status"),
        ("POST", "/api/v1/users/me/heartbeat"),
    }
)


def resolve_operation(method: str, path: str, tags: list[str]) -> tuple[Scope, OperationPolicy]:
    """Resolve the effective Scope and OperationPolicy for one operation.

    `tags` is the OpenAPI operation's tag list (empty means untagged, mapped
    to the synthetic "<no-tag>" key). Raises KeyError if any tag isn't in
    TAG_POLICY - callers should let that propagate as a hard failure, not
    catch it, since an unclassified tag is exactly the failure mode this
    file exists to prevent.
    """
    tag = tags[0] if tags else "<no-tag>"
    tag_scope = TAG_POLICY[tag]  # KeyError is intentional - see docstring
    override = OPERATION_OVERRIDES.get((method.upper(), path))

    if override is None:
        return tag_scope, OperationPolicy(None)

    effective_scope = override.scope_override if override.scope_override is not None else tag_scope
    return effective_scope, override


def is_operation_included(method: str, path: str, tags: list[str]) -> bool:
    """Whether this operation should generate an MCP tool at all."""
    scope, _policy = resolve_operation(method, path, tags)
    if scope == Scope.DENY:
        return False
    if scope == Scope.ALLOW_READ:
        return method.upper() in ("GET", "HEAD")
    return True  # ALLOW_WRITE: both reads and writes included


_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")


def validate_against_openapi(openapi_spec: dict) -> list[str]:
    """Check this policy file against a live/snapshotted OpenAPI schema.

    Returns a list of human-readable problems; empty means the policy is
    complete and consistent with the schema. This is the single source of
    truth for the "operation-level" completeness check described in the
    plan - both mcp_server/server.py (at real startup, against the schema
    it just fetched) and mcp_server/tests/test_router_policy.py (offline,
    against the committed fixture snapshot) call this same function, so
    there is exactly one implementation of "is every tag/operation
    classified" to keep in sync.

    Two kinds of problem are reported:
    1. A tag present in the schema but missing from TAG_POLICY.
    2. An operation under an ALLOW_WRITE tag, or an operation with a
       scope_override of ALLOW_WRITE, whose mutating (non-GET/HEAD) form
       has no explicit stance on external_side_effect - i.e. it's silently
       inheriting the OperationPolicy default of external_side_effect=False
       via OPERATION_OVERRIDES.get() returning None, rather than an
       explicit entry recording that decision. GET/HEAD operations are
       exempt: a read has no side effect to classify by construction.
    """
    problems: list[str] = []
    seen_tags: set[str] = set()

    for path, path_item in openapi_spec.get("paths", {}).items():
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if op is None:
                continue
            tags = op.get("tags", [])
            tag = tags[0] if tags else "<no-tag>"
            seen_tags.add(tag)

            if tag not in TAG_POLICY:
                problems.append(f"{method.upper()} {path}: tag '{tag}' is not classified in TAG_POLICY")
                continue

            if method.upper() in ("GET", "HEAD"):
                continue  # reads have no external-side-effect decision to make

            if not is_operation_included(method, path, tags):
                continue  # excluded (DENY tag, or a mutating op under an ALLOW_READ tag)

            if (method.upper(), path) not in OPERATION_OVERRIDES and (
                method.upper(), path
            ) not in REVIEWED_ORDINARY_WRITES:
                problems.append(
                    f"{method.upper()} {path} (tag '{tag}'): included mutating operation has no "
                    "recorded external_side_effect decision - add it to OPERATION_OVERRIDES (if it "
                    "needs a standalone tool / scope change) or REVIEWED_ORDINARY_WRITES (if it's an "
                    "ordinary internal write with no external effect)"
                )

    unclassified_extra = set(TAG_POLICY) - seen_tags - {"<no-tag>"}
    # Not treated as a problem: a tag that's classified but currently has no
    # operations in the schema isn't a gap, just unused - only the reverse
    # (schema has a tag, policy doesn't) is a real hole.
    del unclassified_extra

    return problems
