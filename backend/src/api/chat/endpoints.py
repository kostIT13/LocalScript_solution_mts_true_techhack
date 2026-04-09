from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from src.api.auth.dependencies import CurrentUserDependency
from src.api.chat.dependencies import ChatServiceDependency, ChatDependency
from src.api.chat.schemas import (
    ChatBaseResponse, ChatCreate, ChatListResponse,
    ChatMessageRequest, ChatMessageResponse, ChatResponse,
    ChatUpdate, MessageResponse
)
from src.services.agent.lua_agent_graph import lua_agent, AgentState
from src.services.sandbox.sandbox_service import SandboxResult, sandbox_service
from typing import List
import json, logging, asyncio, time


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/chats', tags=["Chats"])


@router.get('/', response_model=List[ChatListResponse])
async def get_user_chats(service: ChatServiceDependency, current_user: CurrentUserDependency):
    return await service.list_chats(user_id=current_user.id, limit=20)


@router.post('/', response_model=ChatResponse, status_code=201)
async def create_chat(data: ChatCreate, service: ChatServiceDependency, current_user: CurrentUserDependency):
    return await service.create_chat(user_id=current_user.id, title=data.title)


@router.get('/{chat_id}', response_model=ChatBaseResponse)
async def get_chat(chat: ChatDependency):
    return chat


@router.patch('/{chat_id}', response_model=ChatBaseResponse)
async def update_chat(data: ChatUpdate, chat: ChatDependency, service: ChatServiceDependency):
    try:
        return await service.update_title(chat_id=chat.id, user_id=chat.user_id, title=data.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete('/{chat_id}', status_code=204)
async def delete_chat(chat: ChatDependency, service: ChatServiceDependency):
    try:
        await service.delete_chat(chat_id=chat.id, user_id=chat.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/{chat_id}/messages', response_model=List[MessageResponse])
async def get_chat_messages(chat: ChatDependency, service: ChatServiceDependency, limit: int = 50):
    return await service.get_messages(chat_id=chat.id, user_id=chat.user_id, limit=limit)


@router.post('/{chat_id}/message', response_model=ChatMessageResponse)
async def send_message(data: ChatMessageRequest, chat: ChatDependency, service: ChatServiceDependency, current_user: CurrentUserDependency):
    msg = await service.process_user_message(chat_id=chat.id, user_id=current_user.id, content=data.query)
    return ChatMessageResponse(
        id=msg.id, role=msg.role.value if hasattr(msg.role, 'value') else msg.role,
        content=msg.content, sources=msg.sources, chat_id=msg.chat_id, created_at=msg.created_at
    )


@router.post('/{chat_id}/message/stream', response_model=None)
async def send_message_stream(data: ChatMessageRequest, chat: ChatDependency, service: ChatServiceDependency, current_user: CurrentUserDependency):
    await service.add_message(chat_id=chat.id, user_id=current_user.id, role="user", content=data.query)

    async def event_stream():
        start_time = time.time()
        try:
            fast_mode = getattr(data, 'fast_mode', False)
            run_tests = getattr(data, 'run_test', False) and not fast_mode  
            
            initial_state: AgentState = {
                "messages": [HumanMessage(content=data.query)],
                "current_code": "",
                "validation_error": None,
                "execution_result": None,
                "attempts": 0,
                "rag_chunks": None,
                "user_id": current_user.id,
                "chat_id": chat.id,
                "run_tests": run_tests,
                "fast_mode": fast_mode,
            }

            logger.info(f"Агент: fast={fast_mode}, sandbox={run_tests}")
            
            timeout = 60.0 if fast_mode else 180.0
            final_state = await asyncio.wait_for(lua_agent.ainvoke(initial_state), timeout=timeout)

            generated_code = final_state.get("current_code", "")
            validation_error = final_state.get("validation_error")
            attempts = final_state.get("attempts", 0)
            rag_chunks = final_state.get("rag_chunks")
            execution_result = final_state.get("execution_result")

            logger.info(f"Готово: код={bool(generated_code)}, попытки={attempts}, время={time.time()-start_time:.1f}s")

            if generated_code:
                for i in range(0, len(generated_code), 150):
                    yield f" {json.dumps({'type': 'code_chunk', 'data': generated_code[i:i+150]}, ensure_ascii=False)}\n\n"

            sandbox_result: SandboxResult | None = execution_result
            if run_tests and generated_code and not validation_error and not sandbox_result:
                try:
                    sandbox_result = await asyncio.wait_for(sandbox_service.execute(generated_code, timeout=5), timeout=10.0)
                    yield f" {json.dumps({'type': 'sandbox_result', 'data': sandbox_result.model_dump()}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    sandbox_result = SandboxResult(success=False, error="Sandbox timeout")

            await service.add_message(
                chat_id=chat.id, user_id=current_user.id, role="assistant",
                content=generated_code or "⚠️ Не удалось сгенерировать",
                metadata_={
                    "sources": [c.filename for c in rag_chunks[:3]] if rag_chunks else [],
                    "validation_error": validation_error,
                    "sandbox_result": sandbox_result.model_dump() if sandbox_result else None,
                    "attempts": attempts, "latency_ms": int((time.time() - start_time) * 1000),
                }
            )

            yield f" {json.dumps({
                'type': 'done', 'code': generated_code,
                'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
                'validation_error': validation_error, 'agent_attempts': attempts,
                'used_rag': bool(rag_chunks), 'total_time_ms': int((time.time() - start_time) * 1000)
            }, ensure_ascii=False)}\n\n"

        except asyncio.TimeoutError:
            logger.error(f"Таймаут агента")
            yield f" {json.dumps({'type': 'error', 'message': 'Генерация заняла слишком много времени'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Ошибка: {e}", exc_info=True)
            yield f" {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield " [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")