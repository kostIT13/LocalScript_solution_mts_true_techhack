from fastapi import APIRouter, status, Depends, Path, HTTPException
from src.api.auth.dependencies import CurrentUserDependency
from src.api.chat.dependencies import ChatServiceDependency, ChatDependency
from src.api.chat.schemas import ChatBaseResponse, ChatCreate, ChatListResponse, ChatMessageRequest, ChatMessageResponse, ChatResponse, ChatUpdate, MessageResponse
from typing import List
from src.models.user import User
from src.models.message import MessageRole
from src.services.prompts.lua_agent_system_prompt import LUA_AGENT_SYSTEM_PROMPT
from src.services.llm.generator import stream_chat
import re
from fastapi.responses import StreamingResponse
import json


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

@router.post('/{chat_id}/message/stream', response_model=None)
async def send_message_stream(
    data: ChatMessageRequest,
    chat: ChatDependency,
    service: ChatServiceDependency,
    current_user: CurrentUserDependency
):
    await service.add_message(
        chat_id=chat.id,
        user_id=current_user.id,
        role="user",
        content=data.query
    )
    async def event_stream():
        history = await service.get_messages(chat.id, current_user.id, limit=10)
        history_dicts = [
            {"role": m.role.value if hasattr(m.role, 'value') else m.role, "content": m.content}
            for m in history
        ]
        context = "\n".join([f"{m['role']}: {m['content']}" for m in history_dicts[-5:]])
        full_prompt = f"{context}\nuser: {data.query}\nassistant:"
        
        full_response = ""
        try:
            async for token in stream_chat(
                prompt=full_prompt,
                system_prompt=LUA_AGENT_SYSTEM_PROMPT,
                temperature=data.temperature,
                num_ctx=data.context_length
            ):
                full_response += token
                yield f" {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
            
            code_match = re.search(r"```lua\s*(.*?)\s*```", full_response, re.DOTALL)
            code_extract = code_match.group(1).strip() if code_match else None
            
            await service.add_message(
                chat_id=chat.id,
                user_id=current_user.id,
                role="assistant",
                content=full_response,
                metadata_={"sources": [], "code_extract": code_extract}
            )
            
            yield f" {json.dumps({'type': 'done', 'code': code_extract}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f" {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")