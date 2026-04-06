from src.services.chat.chat_service import ChatService
from src.core.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import Annotated
from src.api.auth.dependencies import CurrentUserDependency
from src.models.chat import Chat
from fastapi import Depends, Path, status, HTTPException


async def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)

ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]

async def get_chat_or_404(
    current_user: CurrentUserDependency,
    chat_service: ChatServiceDependency,
    chat_id: str = Path(..., description="ID чата")
) -> Chat:
    chat = await chat_service.get_chat(chat_id, current_user.id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или доступ запрещён"
        )
    
    return chat

ChatDependency = Annotated[Chat, Depends(get_chat_or_404)]