from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, func
from datetime import datetime
from typing import List, TYPE_CHECKING
from src.core.database import Base
import uuid

if TYPE_CHECKING:
    from src.models.chat import Chat
    from src.models.generation import CodeGeneration
    from src.models.document import Document


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        index=True,
        default=lambda: str(uuid.uuid4())
    )
    
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="Хеш пароля (bcrypt/argon2)")
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    chats: Mapped[List["Chat"]] = relationship(
        "Chat", 
        back_populates="user", 
        cascade="all, delete-orphan",  
        lazy="selectin" 
    )

    generations: Mapped[List["CodeGeneration"]] = relationship(
        "CodeGeneration", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="user",  
        cascade="all, delete-orphan"
    )
    