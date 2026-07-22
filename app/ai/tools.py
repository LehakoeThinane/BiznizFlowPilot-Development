"""Tool schemas (Groq/OpenAI function-calling format) and business-action
executors for the AI co-pilot. Executors reuse existing services - no new
repository or service methods are added here.

Mutating tools (create_task, update_lead_status, add_note) always require a
"summary" argument the model must fill in - this becomes the human-readable
confirmation-card description shown to the user before anything executes,
with no extra LLM round-trip needed to generate it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task. Only propose this after the user has described what they want done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title."},
                    "description": {"type": "string", "description": "Optional longer description."},
                    "lead_id": {
                        "type": "string",
                        "description": "UUID of a lead to attach this task to - must come from a resolved @lead mention above, never guessed.",
                    },
                    "assigned_to": {
                        "type": "string",
                        "description": "UUID of the assignee, or the literal 'me' for the current user.",
                    },
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "default": "medium"},
                    "due_date": {"type": "string", "description": "ISO date, e.g. 2026-08-01."},
                    "summary": {"type": "string", "description": "One-sentence human-readable summary of this action for a confirmation prompt."},
                },
                "required": ["title", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead_status",
            "description": "Update a lead's status. lead_id must come from a resolved @lead mention above.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "UUID of the lead - must come from a resolved @lead mention above."},
                    "new_status": {"type": "string", "enum": ["new", "contacted", "qualified", "won", "lost"]},
                    "summary": {"type": "string", "description": "One-sentence human-readable summary of this action for a confirmation prompt."},
                },
                "required": ["lead_id", "new_status", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Append a timestamped note to a lead or client. entity_id must come from a resolved @lead or @client mention above.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "enum": ["lead", "client"]},
                    "entity_id": {"type": "string", "description": "UUID of the lead or client - must come from a resolved mention above."},
                    "note_text": {"type": "string"},
                    "summary": {"type": "string", "description": "One-sentence human-readable summary of this action for a confirmation prompt."},
                },
                "required": ["entity_type", "entity_id", "note_text", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current or external information not available in this business's own data.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

MUTATING_ACTION_TYPES = {"create_task", "update_lead_status", "add_note"}


def _resolve_assignee(assigned_to: str | None, current_user: CurrentUser) -> UUID | None:
    if not assigned_to:
        return None
    if assigned_to.strip().lower() in ("me", "myself", "current_user"):
        return current_user.user_id
    return UUID(assigned_to)


def execute_create_task(db: Session, business_id: UUID, current_user: CurrentUser, args: dict[str, Any]) -> dict:
    from app.schemas.task import TaskCreate
    from app.services.task import TaskService

    service = TaskService(db)
    data = TaskCreate(
        title=args["title"],
        description=args.get("description"),
        lead_id=UUID(args["lead_id"]) if args.get("lead_id") else None,
        assigned_to=_resolve_assignee(args.get("assigned_to"), current_user),
        priority=args.get("priority", "medium"),
        due_date=args.get("due_date"),
    )
    task = service.create(business_id, current_user, data)
    return {"task_id": str(task.id), "title": task.title, "status": task.status}


def execute_update_lead_status(db: Session, business_id: UUID, current_user: CurrentUser, args: dict[str, Any]) -> dict:
    from app.schemas.lead import LeadUpdate
    from app.services.lead import LeadService

    service = LeadService(db)
    lead = service.update(business_id, current_user, UUID(args["lead_id"]), LeadUpdate(status=args["new_status"]))
    if not lead:
        raise ValueError("Lead not found")
    return {"lead_id": str(lead.id), "status": lead.status}


def execute_add_note(db: Session, business_id: UUID, current_user: CurrentUser, args: dict[str, Any]) -> dict:
    entity_type = args["entity_type"]
    entity_id = UUID(args["entity_id"])
    note_text = args["note_text"]
    prefix = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] "

    if entity_type == "lead":
        from app.schemas.lead import LeadUpdate
        from app.services.lead import LeadService

        service = LeadService(db)
        lead = service.repo.get(business_id=business_id, entity_id=entity_id)
        if not lead:
            raise ValueError("Lead not found")
        merged = f"{lead.notes}\n{prefix}{note_text}" if lead.notes else f"{prefix}{note_text}"
        updated = service.update(business_id, current_user, lead.id, LeadUpdate(notes=merged))
        return {"lead_id": str(updated.id), "notes": updated.notes}

    if entity_type == "client":
        from app.schemas.customer import CustomerUpdate
        from app.services.customer import CustomerService

        service = CustomerService(db)
        customer = service.repo.get(business_id=business_id, entity_id=entity_id)
        if not customer:
            raise ValueError("Customer not found")
        merged = f"{customer.notes}\n{prefix}{note_text}" if customer.notes else f"{prefix}{note_text}"
        updated = service.update(business_id, current_user, customer.id, CustomerUpdate(notes=merged))
        return {"client_id": str(updated.id), "notes": updated.notes}

    raise ValueError(f"Unsupported entity_type: {entity_type}")


ACTION_EXECUTORS = {
    "create_task": execute_create_task,
    "update_lead_status": execute_update_lead_status,
    "add_note": execute_add_note,
}
