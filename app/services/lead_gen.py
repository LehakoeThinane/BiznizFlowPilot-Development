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


@dataclass
class LeadGenResult:
    leads: list[Lead]
    skipped_duplicates: int


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
        skipped = 0

        for place in places:
            external_ref = f"google_places:{place.place_id}"
            if self.customer_repo.get_by_external_ref(business_id, external_ref):
                skipped += 1
                continue

            email = find_email(place.website) if place.website else None

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

            lead = self._lead_service.create(
                business_id,
                current_user,
                LeadCreate(
                    customer_id=customer.id,
                    status="new",
                    source="google_places",
                    assigned_to=assign_to,
                    notes=f'Auto-found via Google Places search: "{query}"',
                ),
            )
            created.append(lead)

        return LeadGenResult(leads=created, skipped_duplicates=skipped)
