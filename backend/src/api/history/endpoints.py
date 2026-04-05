from fastapi import APIRouter, Depends
from src.api.generate.schemas import GenerationListResponse
from src.api.generate.dependencies import GenerationServiceDependency


router = APIRouter()

@router.get("/", response_model=GenerationListResponse, summary="История генераций пользователя")
async def get_history(
    service: GenerationServiceDependency,
    user_id: str = "dev-user-temp",
    limit: int = 20
):
    items = await service.get_user_history(user_id, limit)
    return {"items": items, "total": len(items)}