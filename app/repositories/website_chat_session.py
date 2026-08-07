"""WebsiteChatSession repository - not business_id-scoped (not a
BaseRepository subclass): the token itself is the lookup key and is
already globally unique, same convention as other public-endpoint
token repositories in this codebase."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.website_chat_session import WebsiteChatSession


class WebsiteChatSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_token(self, token: str) -> Optional[WebsiteChatSession]:
        return self.db.query(WebsiteChatSession).filter(WebsiteChatSession.token == token).first()

    def create(self, token: str, conversation_id) -> WebsiteChatSession:
        session = WebsiteChatSession(token=token, conversation_id=conversation_id)
        self.db.add(session)
        return session
