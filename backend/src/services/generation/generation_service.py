import logging
from typing import Optional, List, Dict, Any
from src.services.generation.base import GenerationRepository
from src.models.generation import CodeGeneration, GenerationStatus
import uuid


logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(self, repository: GenerationRepository):
        self.repository = repository

    async def create_generation(
        self,
        user_id: str,
        task: str,
        language: str = "lua",
        model_name: str = "qwen2.5-coder:1.5b",
        temperature: float = 0.2,
        context_length: int = 4096
    ) -> CodeGeneration:
        if not user_id or not task:
            raise ValueError("user_id и task обязательны")

        data = {
            "user_id": user_id,
            "task": task,
            "language": language,
            "model_name": model_name,
            "temperature": temperature,
            "context_length": context_length,
            "validation_status": GenerationStatus.PENDING.value,
            "attempts_count": 1,
        }
        return await self.repository.create(data)

    async def get_generation(self, generation_id: str) -> Optional[CodeGeneration]:
        if not generation_id:
            raise ValueError("generation_id обязателен")
        return await self.repository.get_generation(generation_id)

    async def get_user_history(self, user_id: str, limit: int = 20) -> List[CodeGeneration]:
        if not user_id:
            raise ValueError("user_id обязателен")
        limit = max(1, min(limit, 100))
        return await self.repository.get_user_history(user_id, limit)

    async def update_generation(
        self,
        generation_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[CodeGeneration]:
        if not generation_id:
            raise ValueError("generation_id обязателен")

        allowed_fields = {
            "generated_code", "validation_status", "validation_log",
            "attempts_count", "tokens_prompt", "tokens_completion", "latency_ms", "language"
        }

        safe_update = {}
        for field, value in update_data.items():
            if field in allowed_fields:
                if field == "validation_status" and isinstance(value, GenerationStatus):
                    value = value.value
                safe_update[field] = value

        if safe_update.get("validation_status") == GenerationStatus.RETRY.value:
            current = await self.repository.get_generation(generation_id)
            if current:
                safe_update["attempts_count"] = current.attempts_count + 1

        return await self.repository.update(generation_id, safe_update)

    async def delete_generation(self, generation_id: str) -> bool:
        if not generation_id:
            raise ValueError("generation_id обязателен")
        return await self.repository.delete(generation_id)