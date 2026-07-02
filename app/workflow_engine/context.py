"""Workflow context resolution helpers.

Phase 6 introduces reusable context utilities that:
- resolve dotted field paths (for example ``lead.email``)
- cache loaded entities for one action execution
- render templates using resolved values
"""

from __future__ import annotations

from collections.abc import Mapping
from string import Formatter
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Customer, Lead, Task

_ENTITY_MODELS = {
    "lead": Lead,
    "customer": Customer,
    "task": Task,
}

# Explicit template context allowlist per entity.
# Internal IDs, tenant keys, and timestamps are intentionally excluded.
_CONTEXT_FIELD_ALLOWLIST = {
    "lead": ("status", "source", "value", "notes"),
    "customer": ("name", "email", "phone", "company", "notes"),
    "task": (
        "title",
        "description",
        "status",
        "priority",
        "due_date",
        "completed_at",
    ),
}

# Cache lifetime is one run execution. Entity data resolved as None
# is cached as None for the duration of the run. This is intentional
# for performance but means mid-run data changes are not reflected.
_CACHE_KEY = "_workflow_context_cache"


class MissingTemplateValueError(ValueError):
    """Raised when template rendering requires a missing field value.

    Handlers must catch this and return ActionResult(
        status="failure",
        failure_type=ActionFailureType.TERMINAL,  # or SKIPPABLE if appropriate
        message=str(e),
    )
    rather than letting it propagate to the executor.
    """

    def __init__(self, field_path: str):
        super().__init__(f"Missing template value for field '{field_path}'")
        self.field_path = field_path


def resolve_field_path(db: Session, context: dict[str, Any], field_path: str) -> Any | None:
    """Resolve one dotted field path from workflow action context.

    Resolution is bounded and cached:
    - each entity row is loaded at most once per context
    - each resolved field path is cached for repeated access
    """
    normalized_path = field_path.strip()
    if not normalized_path:
        return None

    cache = _get_context_cache(context)
    resolved_paths = cache["resolved_paths"]
    if normalized_path in resolved_paths:
        return resolved_paths[normalized_path]

    raw_parts = normalized_path.split(".")
    if any(not part.strip() for part in raw_parts):
        resolved_paths[normalized_path] = None
        return None
    parts = [part.strip().lower() for part in raw_parts]

    root = parts[0]
    segments = parts[1:]
    payload = _build_root_payload(db, context, root)

    if payload is None:
        value = None
    elif not segments:
        value = payload
    else:
        value = _traverse(payload, segments)

    resolved_paths[normalized_path] = value
    return value


def resolve_template_values(db: Session, context: dict[str, Any], template: str) -> dict[str, Any | None]:
    """Resolve all placeholder fields referenced by a template string."""
    values: dict[str, Any | None] = {}
    for field_name in _extract_template_fields(template):
        values[field_name] = resolve_field_path(db, context, field_name)
    return values


def render_template(
    template: str,
    values: Mapping[str, Any],
    *,
    strict: bool = True,
    missing_value: str = "",
) -> str:
    """Render a template with pre-resolved values.

    By default (`strict=True`), missing/None values raise
    ``MissingTemplateValueError`` so handlers can classify failures explicitly.
    """
    formatter = Formatter()
    rendered_parts: list[str] = []

    for literal, field_name, format_spec, conversion in formatter.parse(template):
        rendered_parts.append(literal)
        if field_name is None:
            continue

        key = field_name.strip()
        if not key:
            continue

        value = values.get(key)
        if value is None:
            if strict:
                raise MissingTemplateValueError(key)
            value = missing_value

        value = _apply_conversion(value, conversion)
        if format_spec:
            rendered_parts.append(format(value, format_spec))
        else:
            rendered_parts.append(str(value))

    return "".join(rendered_parts)


def render_template_with_context(
    db: Session,
    context: dict[str, Any],
    template: str,
    *,
    strict: bool = True,
    missing_value: str = "",
) -> str:
    """Resolve template fields from context and render in one call."""
    values = resolve_template_values(db, context, template)
    return render_template(
        template=template,
        values=values,
        strict=strict,
        missing_value=missing_value,
    )


def _extract_template_fields(template: str) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if field_name is None:
            continue
        normalized = field_name.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        fields.append(normalized)
    return fields


def _apply_conversion(value: Any, conversion: str | None) -> Any:
    if conversion is None:
        return value
    if conversion == "r":
        return repr(value)
    if conversion == "s":
        return str(value)
    if conversion == "a":
        return ascii(value)
    return value


def _get_context_cache(context: dict[str, Any]) -> dict[str, Any]:
    cache = context.get(_CACHE_KEY)
    if isinstance(cache, dict):
        return cache

    cache = {
        "entities": {},
        "root_entities": {},
        "root_payloads": {},
        "resolved_paths": {},
    }
    context[_CACHE_KEY] = cache
    return cache


def _build_root_payload(db: Session, context: dict[str, Any], root: str) -> dict[str, Any] | None:
    cache = _get_context_cache(context)
    payload_cache: dict[str, dict[str, Any] | None] = cache["root_payloads"]
    if root in payload_cache:
        return payload_cache[root]

    entity = _resolve_root_entity(db, context, root)
    if entity is None:
        payload_cache[root] = None
        return None

    if root == "customer":
        payload = _model_to_context_dict(entity, "customer")
    elif root == "lead":
        payload = _build_lead_payload(db, context, entity)
    elif root == "task":
        payload = _build_task_payload(db, context, entity)
    else:
        payload = _model_to_context_dict(entity, root)

    payload_cache[root] = payload
    return payload


def _build_lead_payload(db: Session, context: dict[str, Any], lead: Lead) -> dict[str, Any]:
    payload = _model_to_context_dict(lead, "lead")
    customer = None
    if lead.customer_id:
        customer = _fetch_entity(db, context, "customer", lead.customer_id)

    customer_payload = _model_to_context_dict(customer, "customer") if customer is not None else None
    payload["customer"] = customer_payload
    # Convenience aliases used by templates such as {lead.name} / {lead.email}.
    payload["name"] = customer_payload.get("name") if customer_payload else None
    payload["email"] = customer_payload.get("email") if customer_payload else None
    payload["company"] = customer_payload.get("company") if customer_payload else None
    return payload


def _build_task_payload(db: Session, context: dict[str, Any], task: Task) -> dict[str, Any]:
    payload = _model_to_context_dict(task, "task")

    lead_payload: dict[str, Any] | None = None
    if task.lead_id:
        lead = _fetch_entity(db, context, "lead", task.lead_id)
        if lead is not None:
            lead_payload = _build_lead_payload(db, context, lead)

    payload["lead"] = lead_payload
    payload["customer"] = lead_payload.get("customer") if isinstance(lead_payload, dict) else None
    return payload


def _resolve_root_entity(db: Session, context: dict[str, Any], root: str) -> Lead | Customer | Task | None:
    cache = _get_context_cache(context)
    root_entities: dict[str, Lead | Customer | Task | None] = cache["root_entities"]
    if root in root_entities:
        return root_entities[root]

    primary_type = _normalize_entity_name(context.get("entity_type"))
    primary_id = context.get("entity_id")
    primary_entity = _fetch_entity(db, context, primary_type, primary_id)

    resolved: Lead | Customer | Task | None = None
    if root == primary_type:
        resolved = primary_entity
    elif root == "lead" and primary_type == "task" and isinstance(primary_entity, Task):
        resolved = _fetch_entity(db, context, "lead", primary_entity.lead_id)
    elif root == "customer":
        if primary_type == "customer":
            resolved = primary_entity if isinstance(primary_entity, Customer) else None
        elif primary_type == "lead" and isinstance(primary_entity, Lead):
            resolved = _fetch_entity(db, context, "customer", primary_entity.customer_id)
        elif primary_type == "task" and isinstance(primary_entity, Task):
            lead = _fetch_entity(db, context, "lead", primary_entity.lead_id)
            if isinstance(lead, Lead):
                resolved = _fetch_entity(db, context, "customer", lead.customer_id)

    root_entities[root] = resolved
    return resolved


def _normalize_entity_name(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    return raw.strip().lower()


def _fetch_entity(
    db: Session,
    context: dict[str, Any],
    entity_type: str,
    entity_id: Any,
) -> Lead | Customer | Task | None:
    normalized_type = _normalize_entity_name(entity_type)
    model = _ENTITY_MODELS.get(normalized_type)
    if model is None:
        return None

    business_id = _coerce_uuid(context.get("business_id"))
    record_id = _coerce_uuid(entity_id)
    if business_id is None or record_id is None:
        return None

    cache = _get_context_cache(context)
    entities: dict[tuple[str, str], Lead | Customer | Task | None] = cache["entities"]
    cache_key = (normalized_type, str(record_id))
    if cache_key in entities:
        return entities[cache_key]

    entity = (
        db.query(model)
        .filter(
            model.id == record_id,
            model.business_id == business_id,
        )
        .first()
    )
    entities[cache_key] = entity
    return entity


def _model_to_context_dict(model: Any, entity_type: str) -> dict[str, Any]:
    if model is None:
        return {}

    normalized_type = _normalize_entity_name(entity_type)
    allowed_fields = _CONTEXT_FIELD_ALLOWLIST.get(normalized_type)
    if not allowed_fields:
        return {}

    return {field: getattr(model, field, None) for field in allowed_fields}


def _coerce_uuid(raw: Any) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        try:
            return UUID(raw)
        except ValueError:
            return None
    return None


def _traverse(payload: Any, segments: list[str]) -> Any | None:
    current = payload
    for segment in segments:
        if current is None:
            return None

        if isinstance(current, Mapping):
            current = current.get(segment)
            continue

        if hasattr(current, segment):
            current = getattr(current, segment)
            continue

        return None

    return current
