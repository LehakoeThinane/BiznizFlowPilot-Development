"""Shared template rendering utilities for workflow actions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.workflow_engine.context import render_template_with_context


def render_template_string(db: Session, context: dict[str, Any], template: str) -> str:
    """Render one template string using workflow context.

    Contract:
    - Missing template values raise MissingTemplateValueError from the context
      renderer (strict mode).
    - This helper never substitutes missing placeholders silently.
    - Rendering errors are propagated to callers for explicit classification.
    """
    return render_template_with_context(db, context, template)


def render_template_value(
    db: Session,
    context: dict[str, Any],
    value: Any,
    *,
    max_depth: int = 10,
    _depth: int = 0,
) -> Any:
    """Render template placeholders inside a nested value recursively.

    Raises:
    - ValueError when nested structures exceed max_depth.
    """
    if _depth > max_depth:
        raise ValueError(f"Template payload nesting exceeds max_depth={max_depth}")
    if isinstance(value, str):
        return render_template_string(db, context, value)
    if isinstance(value, list):
        return [
            render_template_value(
                db,
                context,
                item,
                max_depth=max_depth,
                _depth=_depth + 1,
            )
            for item in value
        ]
    if isinstance(value, Mapping):
        return {
            str(key): render_template_value(
                db,
                context,
                nested_value,
                max_depth=max_depth,
                _depth=_depth + 1,
            )
            for key, nested_value in value.items()
        }
    return value
