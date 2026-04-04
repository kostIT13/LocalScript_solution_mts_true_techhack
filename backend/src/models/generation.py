from src.core.database import Base
from sqlalchemy.orm import Mapped, mapped_column
import enum
from sqlalchemy import String, ForeignKey


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"           
    SUCCESS = "success"           
    SYNTAX_ERROR = "syntax_error" 
    LINT_ERROR = "lint_error"     
    FAILED = "failed"             
    RETRY = "retry"


class CodeGeneration(Base):
    __tablename__ = 'code_getrations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    

    