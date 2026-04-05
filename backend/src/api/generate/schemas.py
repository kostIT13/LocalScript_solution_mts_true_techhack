from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from src.models.generation import GenerationStatus


class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000, description="Задача для генерации Lua-кода")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="Креативность (0=точно, 1=рандом)")
    context_length: int = Field(4096, ge=512, le=8192, description="Размер контекста (num_ctx)")

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