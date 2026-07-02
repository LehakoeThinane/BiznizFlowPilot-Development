"""Workflow condition evaluation engine."""

from typing import Any, List, Dict
from app.workflow_engine.context import _traverse

def evaluate_conditions(conditions: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
    """Evaluate a list of conditions against a given context.
    
    All conditions must evaluate to True for this to return True (AND logic).
    If no conditions are provided, it returns True.
    
    Expected condition dictionary structure:
    {
        "field": "event.data.status",
        "operator": "==",
        "value": "won"
    }
    """
    if not conditions:
        return True
        
    for condition in conditions:
        if not evaluate_single_condition(condition, context):
            return False
            
    return True

def evaluate_single_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Evaluate a single condition against the context."""
    field_path = condition.get("field")
    operator = condition.get("operator")
    expected_value = condition.get("value")

    if not field_path or not operator:
        # Invalid conditions are treated as false
        return False
        
    actual_value = get_nested(context, field_path)
    
    if operator == "==":
        return actual_value == expected_value
    elif operator == "!=":
        return actual_value != expected_value
    elif operator == ">":
        if actual_value is None or expected_value is None:
            return False
        try:
            return float(actual_value) > float(expected_value)
        except (ValueError, TypeError):
            return str(actual_value) > str(expected_value)
    elif operator == ">=":
        if actual_value is None or expected_value is None:
            return False
        try:
            return float(actual_value) >= float(expected_value)
        except (ValueError, TypeError):
            return str(actual_value) >= str(expected_value)
    elif operator == "<":
        if actual_value is None or expected_value is None:
            return False
        try:
            return float(actual_value) < float(expected_value)
        except (ValueError, TypeError):
            return str(actual_value) < str(expected_value)
    elif operator == "<=":
        if actual_value is None or expected_value is None:
            return False
        try:
            return float(actual_value) <= float(expected_value)
        except (ValueError, TypeError):
            return str(actual_value) <= str(expected_value)
    elif operator == "contains":
        if actual_value is None or expected_value is None:
            return False
        try:
            return expected_value in actual_value
        except TypeError:
            return str(expected_value) in str(actual_value)
    elif operator == "not_contains":
        if actual_value is None or expected_value is None:
            return True
        try:
            return expected_value not in actual_value
        except TypeError:
            return str(expected_value) not in str(actual_value)
    elif operator == "in":
        if actual_value is None or expected_value is None:
            return False
        if not isinstance(expected_value, (list, set, tuple)):
            expected_value = [expected_value]
        return actual_value in expected_value
    elif operator == "not_in":
        if actual_value is None or expected_value is None:
            return True
        if not isinstance(expected_value, (list, set, tuple)):
            expected_value = [expected_value]
        return actual_value not in expected_value
    elif operator == "exists":
        return actual_value is not None
    elif operator == "not_exists":
        return actual_value is None
    else:
        # Unknown operator
        return False

def get_nested(context: Dict[str, Any], field_path: str) -> Any:
    """Retrieve a value from a nested dictionary structure using a dotted path."""
    if not field_path:
        return None
        
    parts = field_path.strip().split(".")
    if any(not part.strip() for part in parts):
        return None
        
    segments = [part.strip() for part in parts]
    
    return _traverse(context, segments)
