"""Tests for workflow condition evaluation engine."""

import pytest
from app.workflow_engine.condition_evaluator import (
    evaluate_conditions,
    evaluate_single_condition,
    get_nested,
)

CTX = {
    "event": {
        "data": {
            "status": "won",
            "amount": 500,
            "tags": ["vip", "enterprise"],
        },
        "type": "lead_status_changed",
    },
    "lead": {
        "id": "abc-123",
        "score": 75,
    },
    "business_id": "biz-001",
}


# ── get_nested ────────────────────────────────────────────────────────────────

class TestGetNested:
    def test_top_level_key(self):
        assert get_nested(CTX, "business_id") == "biz-001"

    def test_nested_two_levels(self):
        assert get_nested(CTX, "event.type") == "lead_status_changed"

    def test_nested_three_levels(self):
        assert get_nested(CTX, "event.data.status") == "won"

    def test_missing_key_returns_none(self):
        assert get_nested(CTX, "event.data.missing") is None

    def test_empty_path_returns_none(self):
        assert get_nested(CTX, "") is None

    def test_path_with_spaces_is_stripped(self):
        assert get_nested(CTX, " event . data . status ") == "won"

    def test_path_with_empty_segment_returns_none(self):
        assert get_nested(CTX, "event..data") is None

    def test_missing_top_level_returns_none(self):
        assert get_nested(CTX, "nonexistent.key") is None


# ── evaluate_conditions ───────────────────────────────────────────────────────

class TestEvaluateConditions:
    def test_empty_list_returns_true(self):
        assert evaluate_conditions([], CTX) is True

    def test_all_conditions_true(self):
        conds = [
            {"field": "event.data.status", "operator": "==", "value": "won"},
            {"field": "lead.score", "operator": ">", "value": 50},
        ]
        assert evaluate_conditions(conds, CTX) is True

    def test_one_condition_false_short_circuits(self):
        conds = [
            {"field": "event.data.status", "operator": "==", "value": "won"},
            {"field": "lead.score", "operator": ">", "value": 100},
        ]
        assert evaluate_conditions(conds, CTX) is False


# ── evaluate_single_condition: equality operators ─────────────────────────────

class TestEqualityOperators:
    def test_eq_match(self):
        c = {"field": "event.data.status", "operator": "==", "value": "won"}
        assert evaluate_single_condition(c, CTX) is True

    def test_eq_no_match(self):
        c = {"field": "event.data.status", "operator": "==", "value": "lost"}
        assert evaluate_single_condition(c, CTX) is False

    def test_neq_match(self):
        c = {"field": "event.data.status", "operator": "!=", "value": "lost"}
        assert evaluate_single_condition(c, CTX) is True

    def test_neq_no_match(self):
        c = {"field": "event.data.status", "operator": "!=", "value": "won"}
        assert evaluate_single_condition(c, CTX) is False


# ── evaluate_single_condition: numeric comparison operators ───────────────────

class TestNumericOperators:
    def test_gt_true(self):
        c = {"field": "event.data.amount", "operator": ">", "value": 100}
        assert evaluate_single_condition(c, CTX) is True

    def test_gt_false(self):
        c = {"field": "event.data.amount", "operator": ">", "value": 1000}
        assert evaluate_single_condition(c, CTX) is False

    def test_gt_none_value_returns_false(self):
        c = {"field": "event.data.missing", "operator": ">", "value": 0}
        assert evaluate_single_condition(c, CTX) is False

    def test_gte_equal(self):
        c = {"field": "event.data.amount", "operator": ">=", "value": 500}
        assert evaluate_single_condition(c, CTX) is True

    def test_gte_less(self):
        c = {"field": "event.data.amount", "operator": ">=", "value": 501}
        assert evaluate_single_condition(c, CTX) is False

    def test_gte_none_returns_false(self):
        c = {"field": "event.data.missing", "operator": ">=", "value": 0}
        assert evaluate_single_condition(c, CTX) is False

    def test_lt_true(self):
        c = {"field": "lead.score", "operator": "<", "value": 100}
        assert evaluate_single_condition(c, CTX) is True

    def test_lt_false(self):
        c = {"field": "lead.score", "operator": "<", "value": 50}
        assert evaluate_single_condition(c, CTX) is False

    def test_lt_none_returns_false(self):
        c = {"field": "event.data.missing", "operator": "<", "value": 100}
        assert evaluate_single_condition(c, CTX) is False

    def test_lte_equal(self):
        c = {"field": "lead.score", "operator": "<=", "value": 75}
        assert evaluate_single_condition(c, CTX) is True

    def test_lte_greater(self):
        c = {"field": "lead.score", "operator": "<=", "value": 74}
        assert evaluate_single_condition(c, CTX) is False

    def test_lte_none_returns_false(self):
        c = {"field": "event.data.missing", "operator": "<=", "value": 0}
        assert evaluate_single_condition(c, CTX) is False

    def test_numeric_string_fallback(self):
        ctx = {"val": "b"}
        c = {"field": "val", "operator": ">", "value": "a"}
        assert evaluate_single_condition(c, ctx) is True


# ── evaluate_single_condition: string/collection operators ───────────────────

class TestCollectionOperators:
    def test_contains_true(self):
        c = {"field": "event.data.tags", "operator": "contains", "value": "vip"}
        assert evaluate_single_condition(c, CTX) is True

    def test_contains_false(self):
        c = {"field": "event.data.tags", "operator": "contains", "value": "premium"}
        assert evaluate_single_condition(c, CTX) is False

    def test_contains_none_field_returns_false(self):
        c = {"field": "event.data.missing", "operator": "contains", "value": "x"}
        assert evaluate_single_condition(c, CTX) is False

    def test_not_contains_true(self):
        c = {"field": "event.data.tags", "operator": "not_contains", "value": "premium"}
        assert evaluate_single_condition(c, CTX) is True

    def test_not_contains_false(self):
        c = {"field": "event.data.tags", "operator": "not_contains", "value": "vip"}
        assert evaluate_single_condition(c, CTX) is False

    def test_not_contains_none_field_returns_true(self):
        c = {"field": "event.data.missing", "operator": "not_contains", "value": "x"}
        assert evaluate_single_condition(c, CTX) is True

    def test_in_true(self):
        c = {"field": "event.data.status", "operator": "in", "value": ["won", "qualified"]}
        assert evaluate_single_condition(c, CTX) is True

    def test_in_false(self):
        c = {"field": "event.data.status", "operator": "in", "value": ["lost", "new"]}
        assert evaluate_single_condition(c, CTX) is False

    def test_in_single_value_coerced(self):
        c = {"field": "event.data.status", "operator": "in", "value": "won"}
        assert evaluate_single_condition(c, CTX) is True

    def test_in_none_field_returns_false(self):
        c = {"field": "event.data.missing", "operator": "in", "value": ["won"]}
        assert evaluate_single_condition(c, CTX) is False

    def test_not_in_true(self):
        c = {"field": "event.data.status", "operator": "not_in", "value": ["lost", "new"]}
        assert evaluate_single_condition(c, CTX) is True

    def test_not_in_false(self):
        c = {"field": "event.data.status", "operator": "not_in", "value": ["won"]}
        assert evaluate_single_condition(c, CTX) is False

    def test_not_in_none_field_returns_true(self):
        c = {"field": "event.data.missing", "operator": "not_in", "value": ["won"]}
        assert evaluate_single_condition(c, CTX) is True

    def test_not_in_single_value_coerced(self):
        c = {"field": "event.data.status", "operator": "not_in", "value": "lost"}
        assert evaluate_single_condition(c, CTX) is True


# ── evaluate_single_condition: existence operators ────────────────────────────

class TestExistenceOperators:
    def test_exists_true(self):
        c = {"field": "event.data.status", "operator": "exists"}
        assert evaluate_single_condition(c, CTX) is True

    def test_exists_false(self):
        c = {"field": "event.data.missing", "operator": "exists"}
        assert evaluate_single_condition(c, CTX) is False

    def test_not_exists_true(self):
        c = {"field": "event.data.missing", "operator": "not_exists"}
        assert evaluate_single_condition(c, CTX) is True

    def test_not_exists_false(self):
        c = {"field": "event.data.status", "operator": "not_exists"}
        assert evaluate_single_condition(c, CTX) is False


# ── evaluate_single_condition: edge / error cases ────────────────────────────

class TestEdgeCases:
    def test_missing_field_key_returns_false(self):
        c = {"operator": "==", "value": "won"}
        assert evaluate_single_condition(c, CTX) is False

    def test_missing_operator_key_returns_false(self):
        c = {"field": "event.data.status", "value": "won"}
        assert evaluate_single_condition(c, CTX) is False

    def test_unknown_operator_returns_false(self):
        c = {"field": "event.data.status", "operator": "regex", "value": ".*"}
        assert evaluate_single_condition(c, CTX) is False

    def test_contains_non_iterable_falls_back_to_str(self):
        ctx = {"val": 12345}
        c = {"field": "val", "operator": "contains", "value": "123"}
        assert evaluate_single_condition(c, ctx) is True
