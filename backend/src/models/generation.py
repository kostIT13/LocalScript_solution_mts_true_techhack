from src.core.database import Base
from sqlalchemy.orm import Mapped, mapped_column
import enum
from sqlalchemy import String, ForeignKey, Text, Float, Integer, Enum, Index, DateTime, func
from datetime import datetime
import uuid


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"           
    SUCCESS = "success"           
    SYNTAX_ERROR = "syntax_error" 
    LINT_ERROR = "lint_error"     
    FAILED = "failed"             
    RETRY = "retry"


class CodeGeneration(Base):
    __tablename__ = 'code_generations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task: Mapped[str] = mapped_column(Text, nullable=False, comment='Запрос пользователя')
    generated_code: Mapped[str] = mapped_column(Text, nullable=False, comment='Сгенерированный код')
    language: Mapped[str] = mapped_column(String, default='lua', comment='Язык кода')
    model_name: Mapped[str] = mapped_column(String(50), default="qwen2.5-coder:1.5b", comment="Использованная LLM")
    temperature: Mapped[float] = mapped_column(Float, default=0.2, comment="Температура генерации")
    context_length: Mapped[int] = mapped_column(Integer, default=4096, comment="Размер контекста (num_ctx)")
    validation_status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus, name="generation_status"),
        default=GenerationStatus.PENDING,
        index=True,
        comment="Результат валидации кода"
    )
    validation_log: Mapped[str] = mapped_column(Text, nullable=True, comment="Вывод luac/luacheck или ошибка")
    attempts_count: Mapped[int] = mapped_column(Integer, default=1, comment="Количество попыток генерации/исправления")
    tokens_prompt: Mapped[int] = mapped_column(Integer, nullable=True, comment="Токенов в промпте")
    tokens_completion: Mapped[int] = mapped_column(Integer, nullable=True, comment="Токенов в ответе")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True, comment="Время генерации в мс")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        onupdate=func.now()
    )
    
    __table_args__ = (
        Index("idx_user_created", "user_id", "created_at"),
        Index("idx_status", "validation_status"),
        Index("idx_model", "model_name"),
    )
    
    @property
    def is_valid(self) -> bool:
        return self.validation_status == GenerationStatus.SUCCESS
    
    @property
    def code_preview(self) -> str:
        if not self.generated_code:
            return ""
        preview = self.generated_code[:100].strip()
        return preview + "..." if len(self.generated_code) > 100 else preview
