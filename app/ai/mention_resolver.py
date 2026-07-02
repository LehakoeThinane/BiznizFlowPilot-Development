"""Resolve @mention tokens against real DB records."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.mention_parser import RawMention
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.task import Task
from app.models.user import User


@dataclass
class ResolvedMention:
    mention_type: str
    raw_value: str
    original: str
    found: bool
    entity_id: str | None = None
    display_name: str = ""
    summary: str = ""          # one-line for LLM context
    data: dict = field(default_factory=dict)  # serialised entity fields


def _ilike(col, value: str):
    return col.ilike(f"%{value}%")


def _resolve_client(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(Customer)
        .filter(Customer.business_id == business_id, _ilike(Customer.name, value))
        .first()
    )
    if not row:
        return None
    summary = f'Customer "{row.name}"'
    if row.email:
        summary += f" <{row.email}>"
    if row.company:
        summary += f" ({row.company})"
    return ResolvedMention(
        mention_type="client",
        raw_value=value,
        original=f"@client:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=row.name,
        summary=summary,
        data={"id": str(row.id), "name": row.name, "email": row.email, "phone": row.phone, "company": row.company},
    )


def _resolve_lead(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(Lead)
        .filter(Lead.business_id == business_id)
        .filter(_ilike(Lead.source, value) | _ilike(Lead.notes, value))
        .first()
    )
    if not row:
        # try by ID prefix
        row = db.query(Lead).filter(Lead.business_id == business_id, Lead.id.cast(db.bind.dialect.name and __import__("sqlalchemy").String).ilike(f"{value}%")).first()
    if not row:
        return None
    summary = f'Lead (status={row.status}, value={row.value or "?"})'
    return ResolvedMention(
        mention_type="lead",
        raw_value=value,
        original=f"@lead:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=f"Lead {str(row.id)[:8]}",
        summary=summary,
        data={"id": str(row.id), "status": row.status, "value": row.value, "source": row.source, "notes": row.notes},
    )


def _resolve_task(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(Task)
        .filter(Task.business_id == business_id, _ilike(Task.title, value))
        .first()
    )
    if not row:
        return None
    summary = f'Task "{row.title}" (status={row.status}, priority={row.priority})'
    if row.due_date:
        summary += f", due={row.due_date.date()}"
    return ResolvedMention(
        mention_type="task",
        raw_value=value,
        original=f"@task:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=row.title,
        summary=summary,
        data={"id": str(row.id), "title": row.title, "status": row.status, "priority": row.priority, "due_date": str(row.due_date) if row.due_date else None},
    )


def _resolve_user(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(User)
        .filter(
            User.business_id == business_id,
            _ilike(User.email, value) | _ilike(User.first_name, value) | _ilike(User.last_name, value),
        )
        .first()
    )
    if not row:
        return None
    full_name = f"{row.first_name} {row.last_name}".strip()
    return ResolvedMention(
        mention_type="user",
        raw_value=value,
        original=f"@user:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=full_name or row.email,
        summary=f'User "{full_name}" ({row.email}, role={row.role})',
        data={"id": str(row.id), "email": row.email, "full_name": full_name, "role": row.role},
    )


def _resolve_product(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(Product)
        .filter(
            Product.business_id == business_id,
            _ilike(Product.name, value) | _ilike(Product.sku, value),
        )
        .first()
    )
    if not row:
        return None
    return ResolvedMention(
        mention_type="product",
        raw_value=value,
        original=f"@product:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=row.name,
        summary=f'Product "{row.name}" (SKU={row.sku}, price={row.unit_price})',
        data={"id": str(row.id), "sku": row.sku, "name": row.name, "unit_price": str(row.unit_price)},
    )


def _resolve_supplier(db: Session, business_id: UUID, value: str) -> ResolvedMention | None:
    row = (
        db.query(Supplier)
        .filter(Supplier.business_id == business_id, _ilike(Supplier.name, value))
        .first()
    )
    if not row:
        return None
    return ResolvedMention(
        mention_type="supplier",
        raw_value=value,
        original=f"@supplier:{value}",
        found=True,
        entity_id=str(row.id),
        display_name=row.name,
        summary=f'Supplier "{row.name}" (email={row.email or "—"}, rating={row.rating or "—"})',
        data={"id": str(row.id), "name": row.name, "email": row.email, "rating": row.rating},
    )


_RESOLVERS = {
    "client": _resolve_client,
    "lead": _resolve_lead,
    "task": _resolve_task,
    "user": _resolve_user,
    "product": _resolve_product,
    "supplier": _resolve_supplier,
}


def resolve_mentions(
    mentions: list[RawMention],
    db: Session,
    business_id: UUID,
) -> list[ResolvedMention]:
    """Look up each parsed mention in the DB. Returns one result per input."""
    resolved: list[ResolvedMention] = []
    for m in mentions:
        resolver = _RESOLVERS.get(m.mention_type)
        if resolver:
            result = resolver(db, business_id, m.raw_value)
            if result:
                resolved.append(result)
            else:
                resolved.append(
                    ResolvedMention(
                        mention_type=m.mention_type,
                        raw_value=m.raw_value,
                        original=m.original,
                        found=False,
                        display_name=m.raw_value,
                        summary=f"No {m.mention_type} found matching '{m.raw_value}'",
                    )
                )
        # unsupported type → silently skip
    return resolved


def search_mentions(
    mention_type: str,
    query: str,
    db: Session,
    business_id: UUID,
    limit: int = 8,
) -> list[dict]:
    """Autocomplete search — returns lightweight list for the frontend picker."""
    q = query.strip()
    results: list[dict] = []

    if mention_type == "client":
        rows = (
            db.query(Customer)
            .filter(Customer.business_id == business_id, _ilike(Customer.name, q))
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": r.name, "sub": r.email or ""} for r in rows]

    elif mention_type == "lead":
        rows = (
            db.query(Lead)
            .filter(Lead.business_id == business_id)
            .filter(_ilike(Lead.source, q) | _ilike(Lead.notes, q))
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": f"Lead {str(r.id)[:8]}", "sub": r.status} for r in rows]

    elif mention_type == "task":
        rows = (
            db.query(Task)
            .filter(Task.business_id == business_id, _ilike(Task.title, q))
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": r.title, "sub": r.status} for r in rows]

    elif mention_type == "user":
        rows = (
            db.query(User)
            .filter(
                User.business_id == business_id,
                _ilike(User.email, q) | _ilike(User.first_name, q) | _ilike(User.last_name, q),
            )
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": f"{r.first_name} {r.last_name}".strip() or r.email, "sub": r.role} for r in rows]

    elif mention_type == "product":
        rows = (
            db.query(Product)
            .filter(Product.business_id == business_id, _ilike(Product.name, q) | _ilike(Product.sku, q))
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": r.name, "sub": r.sku} for r in rows]

    elif mention_type == "supplier":
        rows = (
            db.query(Supplier)
            .filter(Supplier.business_id == business_id, _ilike(Supplier.name, q))
            .limit(limit)
            .all()
        )
        results = [{"id": str(r.id), "label": r.name, "sub": r.email or ""} for r in rows]

    return results
