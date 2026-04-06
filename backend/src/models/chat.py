from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from sqlalchemy import String, ForeignKey, Boolean, func, DateTime
from datetime import datetime
from typing import TYPE_CHECKING, List
import uuid

if TYPE_CHECKING:
    from src.models.message import Message
    from src.models.user import User

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="Новый чат")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="chats")
    messages: Mapped[List["Message"]] = relationship(
        "Message", 
        back_populates="chat", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )