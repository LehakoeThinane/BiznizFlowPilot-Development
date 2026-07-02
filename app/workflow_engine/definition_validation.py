"""Validation helpers for workflow definition configuration."""

from __future__ import annotations

from typing import Any

from app.workflow_engine.action_config import parse_action_config


def validate_and_normalize_definition_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate config.actions and return a normalized payload.

    Contract:
    - config must be an object
    - config.actions must be a non-empty list
    - each action must parse via typed action config validation
    """
    if not isinstance(config, dict):
        raise ValueError("Workflow definition config must be an object")

    raw_actions = config.get("actions")
    if not isinstance(raw_actions, list) or len(raw_actions) == 0:
        raise ValueError("Workflow definition must contain at least one action")

    normalized_actions: list[dict[str, Any]] = []
    for index, raw_action in enumerate(raw_actions):
        if not isinstance(raw_action, dict):
            raise ValueError(f"Invalid action config at index {index}: must be an object")
        try:
            normalized_actions.append(parse_action_config(raw_action).model_dump())
        except Exception as exc:  # noqa: BLE001 - normalize validation errors
            raise ValueError(f"Invalid action config at index {index}: {exc}") from exc

    normalized_config = dict(config)
    normalized_config["actions"] = normalized_actions
    return normalized_config
