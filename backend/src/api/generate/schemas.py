from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from src.models.generation import GenerationStatus
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=1000, description="Задача на естественном языке")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    user_id: str = Field(default="dev-user-temp")
    run_test: bool = Field(default=False, description="Запустить код в Sandbox")
    chat_id: Optional[str] = Field(default=None, description="ID сессии для продолжения диалога")
    feedback: Optional[str] = Field(default=None, description="Обратная связь для улучшения кода")
    context: Optional[dict] = Field(default=None, description="Контекст схемы: wf.vars и wf.initVariables")
    output_var: Optional[str] = Field(default="result", description="Имя переменной результата в ответе")
    
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