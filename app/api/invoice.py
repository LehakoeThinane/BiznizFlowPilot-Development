"""Invoice API — create, list, update status, line items, PDF export."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Annotated
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES
from app.dependencies import get_current_user
from app.models.invoice import Invoice, InvoiceLineItem
from app.schemas.auth import CurrentUser
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceStatusUpdate,
)
from app.services.email import send_invoice_email
from app.services.event import EventService
from app.utils.notify import notify_business

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])

_INVOICE_PREFIX = "INV"


def _require_manager(user: CurrentUser) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Owner or manager required")


def _emit(
    db: Session,
    business_id: Any,
    actor_id: Any,
    event_type: EventType,
    entity_type: str,
    entity_id: Any,
    description: str | None = None,
    data: dict | None = None,
) -> None:
    """Queue an event row in the same (not-yet-committed) transaction as the
    caller's pending business-row change - the caller commits once, after
    this call, so both persist atomically or neither does."""
    EventService(db).create_event(
        business_id=UUID(str(business_id)),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=UUID(str(entity_id)),
        actor_id=UUID(str(actor_id)) if actor_id else None,
        description=description,
        data=data,
        commit=False,
    )


def _next_invoice_number(db: Session, business_id: UUID) -> str:
    count = db.query(sa.func.count(Invoice.id)).filter(
        Invoice.business_id == business_id
    ).scalar() or 0
    return f"{_INVOICE_PREFIX}-{count + 1:05d}"


def _build_line_items(
    invoice_id: UUID, items_data: list
) -> tuple[list[InvoiceLineItem], Decimal, Decimal, Decimal]:
    line_items = []
    subtotal = Decimal("0")
    tax_amount = Decimal("0")
    discount_amount = Decimal("0")
    for item in items_data:
        line_subtotal = item.quantity * item.unit_price
        disc = line_subtotal * (item.discount_percent / Decimal("100"))
        after_disc = line_subtotal - disc
        tax = after_disc * (item.tax_rate / Decimal("100"))
        li = InvoiceLineItem(
            id=uuid4(),
            invoice_id=invoice_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            tax_rate=item.tax_rate,
            subtotal=after_disc + tax,
        )
        line_items.append(li)
        subtotal += line_subtotal
        discount_amount += disc
        tax_amount += tax
    return line_items, subtotal, tax_amount, discount_amount


def _invoice_out(inv: Invoice, db: Session) -> InvoiceOut:
    out = InvoiceOut.model_validate(inv)
    if inv.customer:
        out.customer_name = inv.customer.name
    return out


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    customer_id: UUID | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Invoice).filter(Invoice.business_id == current_user.business_id)
    if status:
        q = q.filter(Invoice.status == status)
    if customer_id:
        q = q.filter(Invoice.customer_id == customer_id)
    total = q.count()
    rows = q.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    items = []
    for inv in rows:
        item = InvoiceListItem.model_validate(inv)
        if inv.customer:
            item.customer_name = inv.customer.name
        items.append(item)
    return InvoiceListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/export")
def export_invoices(
    status: str | None = None,
    customer_id: UUID | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Download all invoices as a CSV file."""
    q = db.query(Invoice).filter(Invoice.business_id == current_user.business_id)
    if status:
        q = q.filter(Invoice.status == status)
    if customer_id:
        q = q.filter(Invoice.customer_id == customer_id)
    rows = q.order_by(Invoice.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Invoice Number", "Customer", "Status",
        "Issue Date", "Due Date",
        "Subtotal (excl. VAT)", "Discount", "VAT (15%)", "Total (incl. VAT)",
        "Notes",
    ])
    for inv in rows:
        writer.writerow([
            inv.invoice_number,
            inv.customer.name if inv.customer else "",
            inv.status,
            inv.issue_date,
            inv.due_date or "",
            inv.subtotal,
            inv.discount_amount,
            inv.tax_amount,
            inv.total_amount,
            inv.notes or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@router.get("/{inv_id}", response_model=InvoiceOut)
def get_invoice(
    inv_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    inv = db.query(Invoice).filter(
        Invoice.id == inv_id, Invoice.business_id == current_user.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_out(inv, db)


@router.get("/{inv_id}/pdf", response_class=HTMLResponse)
def invoice_pdf(
    inv_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Return a print-ready HTML page for the invoice (open in browser → Print → Save as PDF)."""
    inv = db.query(Invoice).filter(
        Invoice.id == inv_id, Invoice.business_id == current_user.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer_name = inv.customer.name if inv.customer else "—"
    rows_html = ""
    for li in inv.line_items:
        rows_html += f"""
        <tr>
          <td>{li.description}</td>
          <td style="text-align:right">{li.quantity}</td>
          <td style="text-align:right">R {li.unit_price:,.2f}</td>
          <td style="text-align:right">{li.discount_percent}%</td>
          <td style="text-align:right">{li.tax_rate}%</td>
          <td style="text-align:right">R {li.subtotal:,.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Invoice {inv.invoice_number}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; font-size: 13px; color: #1a1a1a; padding: 40px; }}
    h1 {{ font-size: 28px; font-weight: 800; color: #1e3a8a; }}
    .meta {{ display: flex; justify-content: space-between; margin: 24px 0; }}
    .block {{ line-height: 1.7; }}
    .block strong {{ display: block; font-size: 11px; text-transform: uppercase;
                     letter-spacing: .05em; color: #666; margin-bottom: 2px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
    th {{ background: #f1f5f9; text-align: left; padding: 8px 10px;
          font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
    .totals {{ margin-top: 16px; text-align: right; }}
    .totals table {{ width: auto; margin-left: auto; }}
    .totals td {{ padding: 4px 10px; border: none; }}
    .totals .total-row td {{ font-size: 16px; font-weight: 700; color: #1e3a8a; }}
    .status {{ display: inline-block; padding: 4px 12px; border-radius: 20px;
               font-size: 11px; font-weight: 700; text-transform: uppercase;
               background: #dbeafe; color: #1e40af; margin-bottom: 8px; }}
    .notes {{ margin-top: 32px; padding: 12px; background: #f8fafc; border-left: 3px solid #1e3a8a; }}
    @media print {{ body {{ padding: 0; }} }}
  </style>
</head>
<body>
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h1>INVOICE</h1>
      <div class="status">{inv.status.upper()}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:20px;font-weight:700">{inv.invoice_number}</div>
      <div style="color:#666">Issued: {inv.issue_date}</div>
      {"<div style='color:#e11d48'>Due: " + str(inv.due_date) + "</div>" if inv.due_date else ""}
    </div>
  </div>

  <div class="meta">
    <div class="block">
      <strong>Bill To</strong>
      {customer_name}<br/>
    </div>
    <div class="block">
      <strong>Payment Terms</strong>
      {inv.payment_terms or "—"}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Description</th>
        <th style="text-align:right">Qty</th>
        <th style="text-align:right">Unit Price</th>
        <th style="text-align:right">Disc %</th>
        <th style="text-align:right">Tax %</th>
        <th style="text-align:right">Amount</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <div class="totals">
    <table>
      <tr><td>Subtotal</td><td>R {inv.subtotal:,.2f}</td></tr>
      {f"<tr><td>Discount</td><td>- R {inv.discount_amount:,.2f}</td></tr>" if inv.discount_amount else ""}
      <tr><td>VAT (15%)</td><td>+ R {inv.tax_amount:,.2f}</td></tr>
      <tr class="total-row"><td>Total (incl. VAT)</td><td>R {inv.total_amount:,.2f}</td></tr>
    </table>
  </div>

  {"<div class='notes'>" + inv.notes + "</div>" if inv.notes else ""}

  <script>window.onload = () => window.print();</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/{inv_id}/send-email")
def send_invoice_by_email(
    inv_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Send the invoice to the customer's email address."""
    _require_manager(current_user)
    inv = db.query(Invoice).filter(
        Invoice.id == inv_id, Invoice.business_id == current_user.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.customer or not inv.customer.email:
        raise HTTPException(status_code=400, detail="Customer has no email address on file")

    # Build the line-items HTML for the email
    rows_html = "".join(
        f"<tr><td style='padding:6px 8px;border-bottom:1px solid #e2e8f0'>{li.description}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>{li.quantity}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>R {li.unit_price:,.2f}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>R {li.subtotal:,.2f}</td></tr>"
        for li in inv.line_items
    )

    send_invoice_email(
        to_email=inv.customer.email,
        customer_name=inv.customer.name,
        invoice_number=inv.invoice_number,
        issue_date=str(inv.issue_date),
        due_date=str(inv.due_date) if inv.due_date else None,
        total_amount=float(inv.total_amount),
        rows_html=rows_html,
        notes=inv.notes,
    )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.INVOICE_SENT, "invoice", inv.id,
          description=f"Invoice {inv.invoice_number} emailed to {inv.customer.email}",
          data={"invoice_number": inv.invoice_number, "to_email": inv.customer.email,
                "total_amount": float(inv.total_amount)})
    db.commit()
    return {"message": f"Invoice {inv.invoice_number} sent to {inv.customer.email}"}


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    data: InvoiceCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    inv_id = uuid4()
    line_items, subtotal, tax_amount, discount_amount = _build_line_items(
        inv_id, data.line_items
    )
    total_amount = subtotal - discount_amount + tax_amount

    inv = Invoice(
        id=inv_id,
        business_id=current_user.business_id,
        invoice_number=_next_invoice_number(db, current_user.business_id),
        customer_id=data.customer_id,
        sales_order_id=data.sales_order_id,
        issue_date=data.issue_date,
        due_date=data.due_date,
        payment_terms=data.payment_terms,
        notes=data.notes,
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        status="draft",
    )
    db.add(inv)
    db.flush()
    for li in line_items:
        db.add(li)
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.INVOICE_CREATED, "invoice", inv.id,
          description=f"Invoice created: {inv.invoice_number} — R{float(inv.total_amount):,.2f}",
          data={"invoice_number": inv.invoice_number, "total_amount": float(inv.total_amount),
                "customer_id": str(inv.customer_id) if inv.customer_id else None})
    db.commit()
    db.refresh(inv)
    return _invoice_out(inv, db)


@router.patch("/{inv_id}/status", response_model=InvoiceOut)
def update_invoice_status(
    inv_id: UUID,
    data: InvoiceStatusUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    inv = db.query(Invoice).filter(
        Invoice.id == inv_id, Invoice.business_id == current_user.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    old_status = inv.status
    inv.status = data.status
    if data.status == "paid":
        inv.paid_at = date.today()
    elif data.status == "sent":
        inv.sent_at = datetime.now(timezone.utc)
    customer_name = inv.customer.name if inv.customer else inv.invoice_number
    notify_business(
        db, current_user.business_id, "order_status",
        f"Invoice {data.status}",
        f"Invoice {inv.invoice_number} for {customer_name} changed from {old_status} to {data.status}.",
        action_url="/invoices", related_type="invoice", related_id=inv.id,
    )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.INVOICE_STATUS_CHANGED, "invoice", inv.id,
          description=f"Invoice {inv.invoice_number} status: {old_status} → {data.status}",
          data={"invoice_number": inv.invoice_number, "old_status": old_status,
                "new_status": data.status, "total_amount": float(inv.total_amount)})
    db.commit()
    db.refresh(inv)
    return _invoice_out(inv, db)


@router.delete("/{inv_id}", status_code=204)
def delete_invoice(
    inv_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    inv = db.query(Invoice).filter(
        Invoice.id == inv_id, Invoice.business_id == current_user.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status not in ("draft",):
        raise HTTPException(status_code=400, detail="Only draft invoices can be deleted")
    inv_id = inv.id
    inv_number = inv.invoice_number
    inv_total = float(inv.total_amount)
    db.delete(inv)
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.INVOICE_DELETED, "invoice", inv_id,
          description=f"Invoice deleted: {inv_number} — R{inv_total:,.2f}",
          data={"invoice_number": inv_number, "total_amount": inv_total})
    db.commit()
