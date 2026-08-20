"""Lead-gen service - pulls prospects from external providers into the CRM.

Each result becomes a real Customer + Lead, created through LeadService so
the same RBAC, event emission, and instant-notification behavior applies
uniformly whether a lead was typed in by hand or found automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.email_scraper import find_email
from app.integrations.google_places import GooglePlacesError, search_text
from app.models.lead import Lead
from app.repositories.customer import CustomerRepository
from app.schemas.auth import CurrentUser
from app.schemas.lead import LeadCreate
from app.services.event import EventService
from app.services.lead import LeadService
from app.services.lead_scoring import MAX_SCORE, is_closed, score_place


@dataclass
class LeadGenResult:
    leads: list[Lead]
    skipped_duplicates: int
    skipped_closed: int = 0
    qualified_count: int = 0


class LeadGenService:
    def __init__(self, db: Session):
        self.db = db
        self.customer_repo = CustomerRepository(db)
        self._lead_service = LeadService(db, event_service=EventService(db))

    def find_via_google_places(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        query: str,
        max_results: int = 10,
        assign_to: UUID | None = None,
    ) -> LeadGenResult:
        try:
            places = search_text(settings.google_places_api_key, query, max_results)
        except GooglePlacesError as e:
            raise ValueError(str(e)) from e

        created: list[Lead] = []
        skipped_duplicates = 0
        skipped_closed = 0
        qualified_count = 0

        for place in places:
            external_ref = f"google_places:{place.place_id}"
            if self.customer_repo.get_by_external_ref(business_id, external_ref):
                skipped_duplicates += 1
                continue

            # A business Google itself reports as closed is not a lead,
            # regardless of how it would otherwise score - excluded entirely
            # rather than imported with a low score.
            if is_closed(place):
                skipped_closed += 1
                continue

            email = find_email(place.website) if place.website else None
            has_website = bool(place.website)

            customer = self.customer_repo.create(
                business_id=business_id,
                commit=False,
                name=place.name,
                phone=place.phone,
                email=email,
                company=place.name,
                website=place.website,
                external_ref=external_ref,
            )

            result = score_place(place, query)
            if result.qualified:
                qualified_count += 1

            # Service-fit angle, not a quality signal: no website at all is
            # the cleanest "they need a site built" signal Places gives us
            # for free; having one just means the pitch is different
            # (systems/automation), not that the lead is worse. Encoded on
            # `source` (not the qualification score) so both the follow-up
            # emailer and staff reviewing the lead know which pitch to use.
            if has_website:
                source = "google_places_has_website"
                angle_note = "Has a website - candidate for a systems/automation review."
            else:
                source = "google_places_no_website"
                angle_note = "No website found - candidate for a new site build."

            notes = f'{angle_note} Auto-found via Google Places search: "{query}"'
            if result.reasons:
                notes += f" - {'; '.join(result.reasons)} (score {result.score}/{MAX_SCORE})."
            else:
                notes += f" - no qualifying signals found (score 0/{MAX_SCORE})."
            lead = self._lead_service.create(
                business_id,
                current_user,
                LeadCreate(
                    customer_id=customer.id,
                    status="qualified" if result.qualified else "new",
                    source=source,
                    assigned_to=assign_to,
                    notes=notes,
                ),
            )
            created.append(lead)

        return LeadGenResult(
            leads=created,
            skipped_duplicates=skipped_duplicates,
            skipped_closed=skipped_closed,
            qualified_count=qualified_count,
        )
