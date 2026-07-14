"""Google Places API (New) client — Text Search only.

Uses the field mask header to request only the fields lead-gen actually
needs, since Places (New) bills per field group requested.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri"


@dataclass
class PlaceResult:
    place_id: str
    name: str
    address: str | None
    phone: str | None
    website: str | None


class GooglePlacesError(Exception):
    """Raised on a non-2xx response from the Places API."""


def search_text(api_key: str, query: str, max_results: int = 10) -> list[PlaceResult]:
    """Run a Places Text Search, e.g. "plumbers in Johannesburg".

    Raises GooglePlacesError on failure - the caller decides how to
    surface that (this module has no opinion on HTTP status codes/logging).
    """
    if not api_key:
        raise GooglePlacesError("Google Places API key is not configured")

    response = httpx.post(
        _SEARCH_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        },
        json={"textQuery": query, "maxResultCount": min(max_results, 20)},
        timeout=15.0,
    )
    if response.status_code != 200:
        raise GooglePlacesError(f"Places API returned {response.status_code}: {response.text[:300]}")

    places = response.json().get("places", [])
    return [
        PlaceResult(
            place_id=place["id"],
            name=place.get("displayName", {}).get("text", "Unknown"),
            address=place.get("formattedAddress"),
            phone=place.get("nationalPhoneNumber"),
            website=place.get("websiteUri"),
        )
        for place in places
    ]
