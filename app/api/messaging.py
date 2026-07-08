"""Direct-message (colleague chat) API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.dependencies import get_current_user
from app.models.messaging import Message
from app.schemas.auth import CurrentUser
from app.schemas.messaging import (
    ConversationCreate,
    ConversationListResponse,
    ConversationSummary,
    DirectMessageOut,
    MessageCreate,
    MessageListResponse,
    UnreadCountResponse,
)
from app.services.messaging import MessagingService

router = APIRouter(
    prefix="/api/v1/messaging", tags=["messaging"], dependencies=[Depends(require_feature("messaging"))]
)


def _message_out(message: Message) -> DirectMessageOut:
    out = DirectMessageOut.model_validate(message)
    out.sender_name = message.sender.full_name if message.sender else ""
    return out


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
def create_or_get_conversation(
    data: ConversationCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        conversation = service.get_or_create_direct_conversation(current_user.business_id, current_user, data.user_id)
        return service.summarize(conversation, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = MessagingService(db)
    return ConversationListResponse(items=service.list_conversations(current_user.business_id, current_user))


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = MessagingService(db)
    return UnreadCountResponse(unread_count=service.unread_count(current_user.business_id, current_user))


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(
    conversation_id: UUID,
    since: datetime | None = None,
    limit: int = 50,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    try:
        service = MessagingService(db)
        messages = service.list_messages(current_user.business_id, current_user, conversation_id, since=since, limit=limit)
        return MessageListResponse(items=[_message_out(m) for m in messages])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/conversations/{conversation_id}/messages", response_model=DirectMessageOut, status_code=201)
def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.send_message(current_user.business_id, current_user, conversation_id, data.content)
        return _message_out(message)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_conversation_read(
    conversation_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        service.mark_read(current_user.business_id, current_user, conversation_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
