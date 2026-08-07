"""WebsiteChatSession model - maps an anonymous browser session (a token
the MM Nexus site's chat widget stores in localStorage) to its Conversation,
so the public widget endpoints never need a JWT/business_id from the
caller - the token itself is the credential, same convention as
app/services/customer_portal.py and app/services/document_share.py."""

from sqlalchemy import Column, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WebsiteChatSession(BaseModel):
    """One anonymous visitor's chat session on the MM Nexus website."""

    __tablename__ = "website_chat_sessions"

    token = Column(String(64), nullable=False, unique=True, index=True)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    conversation = relationship("Conversation")

    def __repr__(self) -> str:
        return f"<WebsiteChatSession id={self.id} conversation_id={self.conversation_id}>"
