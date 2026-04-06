from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, Enum, Text, DateTime, Boolean, func
import enum
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from src.models.user import User


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"      
    PROCESSING = "processing" 
    COMPLETED = "completed"   
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False) 
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False) 
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=True, default="lua_docs") 
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=lambda: {}, nullable=True)  
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())  
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="documents")