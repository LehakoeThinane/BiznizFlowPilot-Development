"""Build the LLM system prompt from business context + resolved mentions."""

from __future__ import annotations

from app.ai.mention_resolver import ResolvedMention

SYSTEM_TEMPLATE = """\
You are an AI assistant embedded in BiznizFlowPilot, a business ERP and CRM system.

Business: {business_name}
User: {user_name} (role: {user_role})
Today: {today}

You help users understand their business data and get things done using natural language.
When users mention entities using @type:value syntax (e.g. @client:Acme, @lead:123),
you receive the resolved data below and can reference it directly in your answer.

You can suggest concrete next steps (e.g. create a task, update a lead, follow up).
Keep replies concise, professional, and actionable.

{entity_context}\
"""


def build_system_prompt(
    business_name: str,
    user_name: str,
    user_role: str,
    today: str,
    resolved_mentions: list[ResolvedMention],
) -> str:
    if resolved_mentions:
        lines = ["── Resolved entity mentions ──"]
        for m in resolved_mentions:
            status = "✓" if m.found else "✗ not found"
            lines.append(f"  {m.original} [{status}] → {m.summary}")
            if m.found and m.data:
                for k, v in m.data.items():
                    if v and k != "id":
                        lines.append(f"      {k}: {v}")
        entity_context = "\n".join(lines) + "\n"
    else:
        entity_context = ""

    return SYSTEM_TEMPLATE.format(
        business_name=business_name,
        user_name=user_name,
        user_role=user_role,
        today=today,
        entity_context=entity_context,
    )
