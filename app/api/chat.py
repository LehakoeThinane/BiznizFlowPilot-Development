"""Chat API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.mention_resolver import search_mentions
from app.core.database import get_db
from app.dependencies import get_current_user
from app.repositories.chat import ChatRepository
from app.schemas.auth import CurrentUser
from app.schemas.chat import (
    ChatConversationDetail,
    ChatConversationOut,
    MentionSearchResult,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.chat import ChatService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/message", response_model=SendMessageResponse)
def send_message(
    data: SendMessageRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Send a message; returns the AI reply and resolved @mentions."""
    if not data.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    service = ChatService(db)
    try:
        return service.send_message(
            message=data.message.strip(),
            business_id=current_user.business_id,
            user_id=current_user.user_id,
            conversation_id=data.conversation_id,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/conversations", response_model=list[ChatConversationOut])
def list_conversations(
    skip: int = 0,
    limit: int = 20,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    repo = ChatRepository(db)
    rows, _ = repo.list_conversations(
        business_id=current_user.business_id,
        user_id=current_user.user_id,
        skip=skip,
        limit=limit,
    )
    return rows


@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetail)
def get_conversation(
    conversation_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    repo = ChatRepository(db)
    conv = repo.get_conversation(conversation_id, current_user.business_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.get("/mentions/search", response_model=list[MentionSearchResult])
def search_mention(
    type: str = Query(..., description="Mention type: client, lead, task, user, product, supplier"),
    q: str = Query("", description="Search query"),
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Autocomplete endpoint for @mention pickers in the UI."""
    results = search_mentions(
        mention_type=type,
        query=q,
        db=db,
        business_id=current_user.business_id,
    )
    return [MentionSearchResult(**r) for r in results]
