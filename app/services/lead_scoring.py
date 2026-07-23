"""Concrete, explainable lead qualification scoring for Google Places results.

Scores each result on three real signals - everything here is derived
directly from data Google Places actually returns, nothing fabricated:

1. Company size (proxy) - Places has no employee-count field at all, so a
   maintained website is the closest available signal that a business has
   some real operating scale, not a one-person outfit with no web presence.
2. Industry match - does Google's own category for this business actually
   overlap with what was searched for? Filters out noise Google's text
   search sometimes includes (e.g. a hardware store showing up in a
   "plumbers" search).
3. Engagement signals - a decent rating *and* a real number of reviews
   behind it, so a single 5-star review doesn't count the same as an
   established business with real customer history.

A business Google itself reports as closed is rejected outright, before
scoring - a closed business is not a lead regardless of how it would
otherwise score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.integrations.google_places import PlaceResult

QUALIFYING_THRESHOLD = 2
MAX_SCORE = 3

_CLOSED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
_STOP_WORDS = {"in", "near", "around", "the", "a", "an", "for", "of", "at", "and"}
_MIN_RATING = 4.0
_MIN_RATING_COUNT = 10


@dataclass
class LeadScore:
    score: int
    qualified: bool
    reasons: list[str] = field(default_factory=list)


def is_closed(place: PlaceResult) -> bool:
    """Whether Google itself reports this business as closed - these are
    rejected before scoring, not just scored low."""
    return place.business_status in _CLOSED_STATUSES


def _industry_keywords(query: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", query.lower())
    keywords = set()
    for word in words:
        if word in _STOP_WORDS or len(word) < 3:
            continue
        # Crude singularization ("plumbers" -> "plumber") - good enough for
        # substring matching against Google's own type strings.
        keywords.add(word[:-1] if word.endswith("s") and not word.endswith("ss") else word)
    return keywords


def _industry_match(query: str, place_types: list[str]) -> bool:
    if not place_types:
        return False
    keywords = _industry_keywords(query)
    normalized_types = [t.replace("_", " ").lower() for t in place_types]
    return any(kw in t or t in kw for kw in keywords for t in normalized_types)


def score_place(place: PlaceResult, query: str) -> LeadScore:
    """Score a single Google Places result against the query it was found
    with. Caller is responsible for checking is_closed() first and skipping
    those results entirely rather than scoring them."""
    score = 0
    reasons: list[str] = []

    if place.website:
        score += 1
        reasons.append("Has a company website")

    if _industry_match(query, place.types):
        score += 1
        reasons.append("Google category matches the search")

    if place.rating is not None and place.rating >= _MIN_RATING and (place.user_rating_count or 0) >= _MIN_RATING_COUNT:
        score += 1
        reasons.append(f"{place.rating:.1f}★ rating from {place.user_rating_count} reviews")

    return LeadScore(score=score, qualified=score >= QUALIFYING_THRESHOLD, reasons=reasons)
