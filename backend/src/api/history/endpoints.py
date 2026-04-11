from typing import Optional
from fastapi import APIRouter, Depends, Query
from src.api.generate.schemas import GenerationListResponse
from src.api.generate.dependencies import GenerationServiceDependency


router = APIRouter(prefix='/history', tags=["History"])

@router.get("/", response_model=GenerationListResponse, summary="История генераций пользователя")
async def get_history(
    service: GenerationServiceDependency,
    user_id: str = Query(default="dev-user-temp", description="ID пользователя"),
    limit: int = Query(default=20, ge=1, le=100, description="Кол-во записей"),
    include_code: bool = Query(default=True, description="Возвращать ли сгенерированный код")
):
    items = await service.get_user_history(user_id, limit)
    
    if not include_code:
        for item in items:
            if hasattr(item, "generated_code"):
                item.generated_code = None
                
    return {"items": items, "total": len(items)}