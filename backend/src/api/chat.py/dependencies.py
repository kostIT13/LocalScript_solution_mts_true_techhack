from src.services.chat.chat_service import ChatService
from src.core.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import Annotated


async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)

ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]