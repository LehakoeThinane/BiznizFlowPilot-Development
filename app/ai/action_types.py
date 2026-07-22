"""Shared dataclasses for LLM engine responses and proposed actions.

Split out from engine.py/tools.py to avoid a circular import: engine.py
needs the tool schemas from tools.py, and tools.py's executors don't need
to know about engines at all, but both need to agree on this shape.
"""

from dataclasses import dataclass, field


@dataclass
class ProposedAction:
    """A mutating tool call the model wants to make, awaiting user confirmation."""

    action_type: str
    arguments: dict
    description: str


@dataclass
class EngineResponse:
    """Result of one full engine.chat() turn, including the final reply text
    and any actions proposed along the way (empty for engines that don't
    support tool-calling)."""

    reply: str
    proposed_actions: list[ProposedAction] = field(default_factory=list)
