from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from src.models.generation import GenerationStatus
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000, description="Задача на естественном языке")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    context_length: int = Field(default=4096, ge=512, le=32768)
    
    # 🔹 Флаги управления режимами
    run_test: bool = Field(default=False, description="Запустить код в sandbox")
    fast_mode: bool = Field(default=False, description="Быстрый режим: меньше контекст, 1 попытка")
    skip_rag: bool = Field(default=None, description="Принудительно пропустить RAG (None=авто)")

class GenerationRecordResponse(BaseModel):
    id: str
    task: str
    generated_code: Optional[str] = None
    validation_status: GenerationStatus
    attempts_count: int
    latency_ms: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class GenerationListResponse(BaseModel):
    items: List[GenerationRecordResponse]
    total: int