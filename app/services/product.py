"""Product service - business logic with auto-event emission."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import OWNER_ONLY, PRIVILEGED_ROLES, require_role
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.auth import CurrentUser


class ProductService:
    """Product service with RBAC and auto-event emission.
    
    🧨 RBAC: Owner/Manager can create/update/delete. Staff can view.
    """

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = ProductRepository(db)
        self._event_service = event_service

    def _emit_event(
        self,
        event_type: EventType,
        business_id: UUID,
        entity_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
        data: dict | None = None,
    ) -> None:
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id,
            event_type=event_type,
            entity_type="product",
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            data=data,
            commit=False,
        )

    def create(self, business_id: UUID, current_user: CurrentUser, data: ProductCreate) -> Product:
        require_role(current_user, PRIVILEGED_ROLES, "create products")

        product = self.repo.create(business_id=business_id, commit=False, **data.model_dump())

        self._emit_event(
            event_type=EventType.PRODUCT_CREATED,
            business_id=business_id,
            entity_id=product.id,
            actor_id=current_user.user_id,
            description=f"Product '{product.name}' created",
            data={"sku": product.sku, "category": product.category},
        )

        self.db.commit()
        self.db.refresh(product)
        return product

    def get(self, business_id: UUID, current_user: CurrentUser, product_id: UUID) -> Product | None:
        return self.repo.get(business_id=business_id, entity_id=product_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Product], int]:
        products = self.repo.list(business_id=business_id, skip=skip, limit=limit)
        total = self.repo.count(business_id=business_id)
        return products, total

    def update(self, business_id: UUID, current_user: CurrentUser, product_id: UUID, data: ProductUpdate) -> Product | None:
        require_role(current_user, PRIVILEGED_ROLES, "update products")

        update_data = data.model_dump(exclude_unset=True)
        product = self.repo.update(business_id=business_id, entity_id=product_id, commit=False, **update_data)

        if product:
            self._emit_event(
                event_type=EventType.PRODUCT_UPDATED,
                business_id=business_id,
                entity_id=product_id,
                actor_id=current_user.user_id,
                description="Product updated",
                data={"updated_fields": list(update_data.keys())},
            )
            self.db.commit()
            self.db.refresh(product)

        return product

    def delete(self, business_id: UUID, current_user: CurrentUser, product_id: UUID) -> bool:
        require_role(current_user, OWNER_ONLY, "delete products")

        product = self.repo.get(business_id=business_id, entity_id=product_id)
        if not product:
            return False

        self._emit_event(
            event_type=EventType.PRODUCT_DELETED,
            business_id=business_id,
            entity_id=product_id,
            actor_id=current_user.user_id,
            description=f"Product deleted (SKU: {product.sku})",
            data={"sku": product.sku},
        )

        self.repo.delete(business_id=business_id, entity_id=product_id, commit=False)
        self.db.commit()
        return True
