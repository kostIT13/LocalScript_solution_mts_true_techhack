from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=1000, description="Задача на естественном языке")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    user_id: str = Field(default="dev-user-temp")
    run_test: bool = Field(default=False, description="Запустить код в Sandbox")
    chat_id: Optional[str] = Field(default=None, description="ID сессии для продолжения диалога")
    feedback: Optional[str] = Field(default=None, description="Обратная связь для улучшения кода")
    use_rag: Optional[bool] = Field(default=None, description="RAG: true=включить, false=выключить, null=авто")