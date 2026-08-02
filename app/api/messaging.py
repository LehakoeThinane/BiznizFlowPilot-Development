"""Direct-message (colleague chat) API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.dependencies import get_current_user
from app.integrations import object_storage
from app.integrations.object_storage import ObjectNotFoundError, ObjectStorageError
from app.models.messaging import Message
from app.models.poll import Poll
from app.schemas.auth import CurrentUser
from app.schemas.messaging import (
    AttachmentDownloadResponse,
    ContactShareCreate,
    ConversationCreate,
    ConversationListResponse,
    ConversationSummary,
    DirectMessageOut,
    EventShareExisting,
    EventShareNew,
    MessageAttachmentOut,
    MessageCreate,
    MessageListResponse,
    PollCreate,
    PollOptionOut,
    PollOut,
    PollVoteRequest,
    SharedCustomerOut,
    SharedMeetingOut,
    StickerCreate,
    UnreadCountResponse,
)
from app.services.message_attachments import MessageAttachmentService
from app.services.messaging import MessagingService

router = APIRouter(
    prefix="/api/v1/messaging", tags=["messaging"], dependencies=[Depends(require_feature("messaging"))]
)


def _poll_out(service: MessagingService, poll: Poll, current_user_id: UUID) -> PollOut:
    tally = service.poll_tally(poll.id)
    my_votes = service.my_poll_vote_option_ids(poll.id, current_user_id)
    options = [PollOptionOut(id=o.id, text=o.text, vote_count=tally.get(o.id, 0)) for o in poll.options]
    return PollOut(
        id=poll.id, question=poll.question, allow_multiple=poll.allow_multiple,
        options=options, my_vote_option_ids=my_votes, total_votes=sum(tally.values()),
    )


def _message_out(service: MessagingService, message: Message, current_user_id: UUID) -> DirectMessageOut:
    out = DirectMessageOut.model_validate(message)
    out.sender_name = message.sender.full_name if message.sender else ""

    if message.attachment:
        attachment = MessageAttachmentOut.model_validate(message.attachment)
        try:
            attachment.download_url = object_storage.presigned_download_url(
                message.attachment.storage_key, message.attachment.filename, disposition="attachment",
            )
        except ObjectStorageError:
            attachment.download_url = None
        out.attachment = attachment

    if message.shared_customer:
        out.shared_customer = SharedCustomerOut.model_validate(message.shared_customer)

    if message.shared_meeting:
        out.shared_meeting = SharedMeetingOut.model_validate(message.shared_meeting)

    if message.poll:
        out.poll = _poll_out(service, message.poll, current_user_id)

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
        return MessageListResponse(items=[_message_out(service, m, current_user.user_id) for m in messages])
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
        return _message_out(service, message, current_user.user_id)
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


# ── Attachments (Document / Photos & videos / Camera / Audio) ──────────────

@router.post("/conversations/{conversation_id}/attachments", response_model=DirectMessageOut, status_code=201)
async def upload_attachment(
    conversation_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    caption: str | None = Form(None),
):
    content = await file.read()
    try:
        attachment_service = MessageAttachmentService(db)
        message = attachment_service.upload(
            current_user.business_id, current_user, conversation_id,
            file.filename or "upload", content, file.content_type, caption,
        )
        return _message_out(MessagingService(db), message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise


@router.get("/attachments/{attachment_id}/download-url", response_model=AttachmentDownloadResponse)
def get_attachment_download_url(
    attachment_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        url = MessageAttachmentService(db).get_download_url(current_user.business_id, current_user, attachment_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ObjectNotFoundError:
        raise HTTPException(status_code=404, detail="This attachment is no longer available in storage.")
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not url:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return AttachmentDownloadResponse(url=url, expires_in=300)


# ── Contact sharing ──────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/contacts", response_model=DirectMessageOut, status_code=201)
def share_contact(
    conversation_id: UUID,
    data: ContactShareCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.share_contact(current_user.business_id, current_user, conversation_id, data.customer_id, data.caption)
        return _message_out(service, message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── Event sharing / scheduling ───────────────────────────────────────────

@router.post("/conversations/{conversation_id}/events/share", response_model=DirectMessageOut, status_code=201)
def share_existing_event(
    conversation_id: UUID,
    data: EventShareExisting,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.share_meeting(current_user.business_id, current_user, conversation_id, data.meeting_id, data.caption)
        return _message_out(service, message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/conversations/{conversation_id}/events/schedule", response_model=DirectMessageOut, status_code=201)
def schedule_new_event(
    conversation_id: UUID,
    data: EventShareNew,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.schedule_and_share_meeting(
            current_user.business_id, current_user, conversation_id,
            data.title, data.description, data.start_time, data.end_time,
            data.call_type, data.participant_user_ids,
        )
        return _message_out(service, message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Stickers ──────────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/stickers", response_model=DirectMessageOut, status_code=201)
def send_sticker(
    conversation_id: UUID,
    data: StickerCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.send_sticker(current_user.business_id, current_user, conversation_id, data.sticker_key)
        return _message_out(service, message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Polls ─────────────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/polls", response_model=DirectMessageOut, status_code=201)
def create_poll(
    conversation_id: UUID,
    data: PollCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        message = service.create_poll(current_user.business_id, current_user, conversation_id, data.question, data.options, data.allow_multiple)
        return _message_out(service, message, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/polls/{poll_id}/vote", response_model=PollOut)
def vote_on_poll(
    poll_id: UUID,
    data: PollVoteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        poll = service.cast_vote(current_user.business_id, current_user, poll_id, data.option_ids)
        return _poll_out(service, poll, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/polls/{poll_id}", response_model=PollOut)
def get_poll(
    poll_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = MessagingService(db)
        poll = service.get_poll(current_user.business_id, current_user, poll_id)
        return _poll_out(service, poll, current_user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
