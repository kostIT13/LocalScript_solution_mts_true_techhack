from fastapi import APIRouter, status, Depends, Path, HTTPException
from src.api.auth.dependencies import CurrentUserDependency
from src.api.chat.dependencies import ChatServiceDependency, ChatDependency
from src.api.chat import ChatBaseResponse, ChatCreate, ChatListResponse, ChatMessageRequest, ChatMessageResponse, ChatResponse, ChatUpdate, MessageResponse
from typing import List
from src.models.user import User
from src.models.message import MessageRole


router = APIRouter(prefix='/chats', tags=["Chats"])


@router.get('/', response_model=List[ChatListResponse])
async def get_user_chats(
    service: ChatServiceDependency,
    current_user: CurrentUserDependency
):
    return await service.list_chats(user_id=current_user.id, limit=20)


@router.post('/', response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    data: ChatCreate,
    service: ChatServiceDependency,
    current_user: CurrentUserDependency
):
    return await service.create_chat(user_id=current_user.id, title=data.title)


@router.get('/{chat_id}', response_model=ChatBaseResponse)
async def get_chat(chat: ChatDependency):
    return chat


@router.patch('/{chat_id}', response_model=ChatBaseResponse)
async def update_chat(
    data: ChatUpdate,
    chat: ChatDependency,
    service: ChatServiceDependency
):
    try:
        return await service.update_title(
            chat_id=chat.id,
            user_id=chat.user_id,
            title=data.title
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete('/{chat_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat: ChatDependency,
    service: ChatServiceDependency
):
    try:
        await service.delete_chat(chat_id=chat.id, user_id=chat.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/{chat_id}/messages', response_model=List[MessageResponse])
async def get_chat_messages(
    chat: ChatDependency,
    service: ChatServiceDependency,
    limit: int = 50
):
    return await service.get_messages(
        chat_id=chat.id,
        user_id=chat.user_id,
        limit=limit
    )


@router.post('/{chat_id}/message', response_model=ChatMessageResponse)
async def send_message(
    data: ChatMessageRequest,
    chat: ChatDependency,
    service: ChatServiceDependency,
    current_user: CurrentUserDependency
):
    
    msg = await service.process_user_message(
        chat_id=chat.id,           
        user_id=current_user.id,
        content=data.query,
    )
    
    return ChatMessageResponse(
        id=msg.id,
        role=msg.role.value if hasattr(msg.role, 'value') else msg.role,
        content=msg.content,
        sources=msg.sources,
        chat_id=msg.chat_id,
        created_at=msg.created_at
    )