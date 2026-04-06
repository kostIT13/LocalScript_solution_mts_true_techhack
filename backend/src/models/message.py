from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from sqlalchemy import String, ForeignKey, Text, Boolean, func, DateTime, Enum as SQLEnum
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import uuid
from enum import Enum  

if TYPE_CHECKING:
    from src.models.chat import Chat

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("chats.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    role: Mapped[str] = mapped_column(
        SQLEnum("user", "assistant", "system", name="message_role"),
        nullable=False, 
        index=True
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=lambda: {}, nullable=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")

    @property
    def sources(self) -> List[str]:
        if not self.metadata_:
            return []
        sources = self.metadata_.get("sources")
        return sources if isinstance(sources, list) else []

    @sources.setter
    def sources(self, value: List[str]):
        if self.metadata_ is None:
            self.metadata_ = {}
        self.metadata_["sources"] = value