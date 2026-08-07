"""Public (unauthenticated) MM Nexus website chat widget endpoints. No auth
dependency on purpose (mirrors app/api/customer_portal.py) - the session
token itself is the credential. See app/services/website_chat.py for the
actual AI-first, human-takeover logic."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.messaging import Message
from app.schemas.website_chat import WidgetMessageOut, WidgetPollResponse, WidgetSendRequest, WidgetSendResponse
from app.services import website_chat
from app.services.website_chat import WebsiteChatNotConfiguredError

public_router = APIRouter(tags=["website-chat-public"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)


def _to_widget_message(message: Message, visitor_id) -> WidgetMessageOut:
    if message.is_ai_reply:
        sender = "ai"
    elif message.sender_id == visitor_id:
        sender = "visitor"
    else:
        sender = "staff"
    return WidgetMessageOut(id=message.id, content=message.content, **{"from": sender}, created_at=message.created_at)


@public_router.post("/api/v1/public/website-chat/messages", response_model=WidgetSendResponse, include_in_schema=False)
@limiter.limit("20/minute")
def send_widget_message(request: Request, body: WidgetSendRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        session_token, messages = website_chat.send_visitor_message(db, body.session_token, body.text)
    except WebsiteChatNotConfiguredError:
        raise HTTPException(status_code=404, detail="The chat widget is not available right now")

    visitor = website_chat.get_or_create_visitor_user(db, UUID(settings.mm_nexus_business_id))
    return WidgetSendResponse(
        session_token=session_token,
        messages=[_to_widget_message(m, visitor.id) for m in messages],
    )


@public_router.get("/api/v1/public/website-chat/messages", response_model=WidgetPollResponse, include_in_schema=False)
@limiter.limit("60/minute")
def poll_widget_messages(
    request: Request, session_token: str, db: Annotated[Session, Depends(get_db)], since: datetime | None = None
):
    try:
        messages = website_chat.list_new_messages(db, session_token, since)
    except WebsiteChatNotConfiguredError:
        raise HTTPException(status_code=404, detail="This chat session is invalid or has expired")

    if not messages or not settings.mm_nexus_business_id:
        return WidgetPollResponse(messages=[])

    visitor = website_chat.get_or_create_visitor_user(db, UUID(settings.mm_nexus_business_id))
    return WidgetPollResponse(messages=[_to_widget_message(m, visitor.id) for m in messages])
