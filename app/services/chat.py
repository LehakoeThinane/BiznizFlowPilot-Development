"""Chat service — orchestrates mention parsing, LLM, and persistence."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.ai.context_builder import build_system_prompt
from app.ai.engine import get_engine
from app.ai.mention_parser import parse_mentions
from app.ai.mention_resolver import resolve_mentions
from app.models.business import Business
from app.models.user import User
from app.repositories.chat import ChatRepository
from app.schemas.chat import SendMessageResponse
from app.core.config import settings


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ChatRepository(db)

    def send_message(
        self,
        message: str,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> SendMessageResponse:
        # 1. Get or create conversation — verify ownership to prevent cross-user access
        if conversation_id:
            conv = self.repo.get_conversation(conversation_id, business_id)
            if not conv or conv.user_id != user_id:
                conversation_id = None
        if not conversation_id:
            title = message[:60] + ("…" if len(message) > 60 else "")
            conv = self.repo.create_conversation(business_id, user_id, title=title)
            conversation_id = conv.id

        # 2. Parse + resolve @mentions
        raw_mentions = parse_mentions(message)
        resolved = resolve_mentions(raw_mentions, self.db, business_id)

        # 3. Load business + user for context
        business = self.db.query(Business).filter(Business.id == business_id).first()
        user = self.db.query(User).filter(User.id == user_id).first()
        business_name = business.name if business else str(business_id)
        user_name = (
            f"{user.first_name} {user.last_name}".strip() if user else str(user_id)
        )
        user_role = user.role if user else "unknown"

        # 4. Build system prompt
        system_prompt = build_system_prompt(
            business_name=business_name,
            user_name=user_name,
            user_role=user_role,
            today=date.today().isoformat(),
            resolved_mentions=resolved,
        )

        # 5. Build message history for LLM
        history = self.repo.get_recent_messages(
            conversation_id, limit=settings.ai_conversation_history_limit
        )
        llm_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
            if msg.role in ("user", "assistant")
        ]
        llm_messages.append({"role": "user", "content": message})

        # 6. Call LLM
        engine = get_engine()
        try:
            reply = engine.chat(llm_messages, system_prompt)
        except Exception as exc:
            reply = f"[AI error: {exc}]"

        # 7. Persist both messages
        mentions_payload = [
            {
                "type": m.mention_type,
                "value": m.raw_value,
                "found": m.found,
                "entity_id": m.entity_id,
                "display_name": m.display_name,
            }
            for m in resolved
        ]
        user_msg = self.repo.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            mentions_data=mentions_payload,
        )
        assistant_msg = self.repo.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
        )
        self.db.commit()

        return SendMessageResponse(
            conversation_id=conversation_id,
            reply=reply,
            resolved_mentions=mentions_payload,
            user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id,
        )
