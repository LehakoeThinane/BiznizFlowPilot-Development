"""Tests for the Google Places lead qualification scoring logic."""

from __future__ import annotations

from app.integrations.google_places import PlaceResult
from app.services.lead_scoring import QUALIFYING_THRESHOLD, is_closed, score_place


def _place(**overrides) -> PlaceResult:
    defaults = dict(
        place_id="place_1", name="Test Co", address="1 Main St", phone="0110000000", website=None,
    )
    defaults.update(overrides)
    return PlaceResult(**defaults)


class TestIsClosed:
    def test_operational_is_not_closed(self):
        assert is_closed(_place(business_status="OPERATIONAL")) is False

    def test_unknown_status_is_not_treated_as_closed(self):
        """Older/incomplete Places responses may omit business_status entirely -
        that's not the same as confirmed-closed, so it must not reject."""
        assert is_closed(_place(business_status=None)) is False

    def test_permanently_closed_is_closed(self):
        assert is_closed(_place(business_status="CLOSED_PERMANENTLY")) is True

    def test_temporarily_closed_is_closed(self):
        assert is_closed(_place(business_status="CLOSED_TEMPORARILY")) is True


class TestScorePlace:
    def test_no_signals_scores_zero_and_is_unqualified(self):
        result = score_place(_place(), query="plumbers in Johannesburg")
        assert result.score == 0
        assert result.qualified is False
        assert result.reasons == []

    def test_website_alone_is_not_enough_to_qualify(self):
        result = score_place(_place(website="https://acme.example"), query="plumbers")
        assert result.score == 1
        assert result.qualified is False

    def test_website_and_industry_match_qualifies(self):
        place = _place(website="https://acme-plumbing.example", types=["plumber", "point_of_interest"])
        result = score_place(place, query="plumbers in Johannesburg")
        assert result.score == 2
        assert result.qualified is True
        assert any("website" in r.lower() for r in result.reasons)
        assert any("category" in r.lower() for r in result.reasons)

    def test_mismatched_industry_does_not_score_a_point(self):
        place = _place(website="https://acme.example", types=["hardware_store"])
        result = score_place(place, query="plumbers in Johannesburg")
        assert result.score == 1
        assert result.qualified is False

    def test_strong_engagement_signal_counts(self):
        place = _place(rating=4.6, user_rating_count=42)
        result = score_place(place, query="plumbers")
        assert result.score == 1
        assert any("review" in r.lower() for r in result.reasons)

    def test_high_rating_with_too_few_reviews_does_not_count(self):
        """A single 5-star review shouldn't score the same as an established
        business with real customer history behind its rating."""
        place = _place(rating=5.0, user_rating_count=2)
        result = score_place(place, query="plumbers")
        assert result.score == 0

    def test_good_rating_but_below_threshold_does_not_count(self):
        place = _place(rating=3.2, user_rating_count=50)
        result = score_place(place, query="plumbers")
        assert result.score == 0

    def test_all_three_signals_hits_max_score(self):
        place = _place(
            website="https://acme-plumbing.example",
            types=["plumber"],
            rating=4.8,
            user_rating_count=120,
        )
        result = score_place(place, query="plumbers in Cape Town")
        assert result.score == 3
        assert result.qualified is True
        assert len(result.reasons) == 3

    def test_qualifying_threshold_is_two_of_three(self):
        assert QUALIFYING_THRESHOLD == 2
