from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from src.core.database import get_db
from src.services.rag.rag_service import RAGService
from typing import Annotated


async def get_rag_service(db: AsyncSession = Depends(get_db)) -> RAGService:
    return RAGService(db_session=db)

RAGServiceDependency = Annotated[RAGService, Depends(get_rag_service)]