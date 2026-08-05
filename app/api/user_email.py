"""Per-user email account API - self-service connect/disconnect, list
inbox, read a message, and send. Every route always uses the caller's own
business_id/user_id - there is no path parameter, this is never
cross-user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.dependencies import get_current_user
from app.integrations import imap_client
from app.integrations.imap_client import ImapAuthenticationError, ImapConnectionError, ImapError
from app.models.user_email import UserEmailAccount
from app.schemas.auth import CurrentUser
from app.schemas.user_email import (
    EmailFolderListResponse,
    EmailFolderResponse,
    EmailListResponse,
    EmailMessageDetail,
    EmailMessageFlagsUpdate,
    EmailMessageSummary,
    EmailSendRequest,
    UserEmailAccountResponse,
    UserEmailAccountUpdate,
)
from app.services.user_email import EmailAccountNotConfiguredError, FolderNotFoundError, UserEmailAccountService
from app.workflow_engine.email_provider import RetryableEmailProviderError, TerminalEmailProviderError

router = APIRouter(
    prefix="/api/v1/email-account", tags=["email"], dependencies=[Depends(require_feature("email"))]
)


def _account_to_response(account: UserEmailAccount | None) -> UserEmailAccountResponse:
    """A missing account isn't an error - "not yet connected" is a normal
    frontend state, so this always returns 200 with all-null/false fields
    rather than 404."""
    if account is None:
        return UserEmailAccountResponse(
            imap_host=None, imap_port=None, imap_username=None, imap_password_set=False,
            smtp_host=None, smtp_port=None, smtp_username=None, smtp_password_set=False,
            smtp_from_email=None, smtp_from_name=None,
        )
    return UserEmailAccountResponse(
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_username=account.imap_username,
        imap_password_set=bool(account.imap_password_encrypted),
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_username=account.smtp_username,
        smtp_password_set=bool(account.smtp_password_encrypted),
        smtp_from_email=account.smtp_from_email,
        smtp_from_name=account.smtp_from_name,
    )


@router.get("", response_model=UserEmailAccountResponse)
def get_email_account(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserEmailAccountResponse:
    service = UserEmailAccountService(db)
    account = service.get_account(current_user.business_id, current_user.user_id)
    return _account_to_response(account)


@router.put("", response_model=UserEmailAccountResponse)
def set_email_account(
    body: UserEmailAccountUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserEmailAccountResponse:
    """Connect or update the caller's own mailbox. Validates the IMAP
    credentials with a real login before persisting anything, so a typo
    doesn't silently save broken credentials."""
    service = UserEmailAccountService(db)
    existing = service.get_account(current_user.business_id, current_user.user_id)

    effective_imap_password = body.imap_password
    if not effective_imap_password and existing and existing.imap_password_encrypted:
        from app.core.crypto import decrypt_secret

        effective_imap_password = decrypt_secret(existing.imap_password_encrypted)

    if not effective_imap_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMAP password is required when connecting for the first time.",
        )

    try:
        imap_client.list_messages(body.imap_host, body.imap_port, body.imap_username, effective_imap_password, limit=1)
    except ImapAuthenticationError:
        raise HTTPException(status_code=400, detail="Login failed - check your IMAP username/password.")
    except ImapConnectionError:
        raise HTTPException(status_code=400, detail="Could not connect - check your IMAP host/port.")

    account = service.set_account(
        current_user.business_id, current_user.user_id,
        imap_host=body.imap_host, imap_port=body.imap_port, imap_username=body.imap_username,
        imap_password=body.imap_password,
        smtp_host=body.smtp_host, smtp_port=body.smtp_port, smtp_username=body.smtp_username,
        smtp_password=body.smtp_password, smtp_from_email=body.smtp_from_email, smtp_from_name=body.smtp_from_name,
    )
    return _account_to_response(account)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_account(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = UserEmailAccountService(db)
    service.delete_account(current_user.business_id, current_user.user_id)


@router.get("/folders", response_model=EmailFolderListResponse)
def list_email_folders(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EmailFolderListResponse:
    service = UserEmailAccountService(db)
    try:
        folders = service.list_folders(current_user.business_id, current_user.user_id)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EmailFolderListResponse(
        items=[EmailFolderResponse(name=f.name, role=f.role) for f in folders]
    )


@router.get("/messages", response_model=EmailListResponse)
def list_email_messages(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    folder: str = Query("inbox"),
) -> EmailListResponse:
    service = UserEmailAccountService(db)
    try:
        messages = service.list_inbox(current_user.business_id, current_user.user_id, limit, offset, folder=folder)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EmailListResponse(
        items=[
            EmailMessageSummary(
                uid=m.uid, from_address=m.from_address, subject=m.subject, date=m.date,
                is_read=m.is_read, is_starred=m.is_starred,
            )
            for m in messages
        ]
    )


@router.get("/messages/{uid}", response_model=EmailMessageDetail)
def get_email_message(
    uid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    folder: str = Query("inbox"),
) -> EmailMessageDetail:
    service = UserEmailAccountService(db)
    try:
        message = service.get_message(current_user.business_id, current_user.user_id, uid, folder=folder)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImapError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return EmailMessageDetail(
        uid=message.uid, from_address=message.from_address, to_address=message.to_address,
        subject=message.subject, date=message.date, body_html=message.body_html, body_text=message.body_text,
        attachment_count=message.attachment_count,
        attachments=[
            {"filename": a.filename, "size": a.size, "content_type": a.content_type} for a in message.attachments
        ],
    )


@router.patch("/messages/{uid}/flags")
def update_email_message_flags(
    uid: str,
    body: EmailMessageFlagsUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    folder: str = Query("inbox"),
) -> dict:
    service = UserEmailAccountService(db)
    try:
        service.set_message_flags(
            current_user.business_id, current_user.user_id, uid, folder=folder,
            is_starred=body.is_starred, is_read=body.is_read,
        )
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImapError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"updated": True}


@router.post("/messages/{uid}/archive")
def archive_email_message(
    uid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    folder: str = Query("inbox"),
) -> dict:
    service = UserEmailAccountService(db)
    try:
        resolved = service.archive_message(current_user.business_id, current_user.user_id, uid, folder=folder)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImapError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"archived": True, "folder": resolved}


@router.delete("/messages/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_message(
    uid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    folder: str = Query("inbox"),
):
    service = UserEmailAccountService(db)
    try:
        service.delete_message(current_user.business_id, current_user.user_id, uid, folder=folder)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ImapAuthenticationError, ImapConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImapError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/send")
def send_email_message(
    body: EmailSendRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    service = UserEmailAccountService(db)
    try:
        service.send_message(current_user.business_id, current_user.user_id, body.to, body.subject, body.body)
    except EmailAccountNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TerminalEmailProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RetryableEmailProviderError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"sent": True}
