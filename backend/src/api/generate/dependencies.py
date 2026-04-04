from src.services.generation.generation_service import GenerationService
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db


async def get_generation_service(db: AsyncSession = Depends(get_db)) -> GenerationService:
    return GenerationService(db)

GenerationServiceDependency = Annotated[GenerationService, Depends(get_generation_service)]