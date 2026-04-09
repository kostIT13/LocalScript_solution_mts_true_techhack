from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from src.api.auth.dependencies import CurrentUserDependency
from src.api.chat.dependencies import ChatServiceDependency, ChatDependency
from src.api.chat.schemas import ChatMessageRequest
from src.services.agent.lua_agent_graph import lua_agent, AgentState
import json, logging, asyncio, time

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/chats', tags=["Chats"])


@router.post('/{chat_id}/message/agent', response_model=None)
async def send_message_agent(
    data: ChatMessageRequest,
    chat: ChatDependency,
    service: ChatServiceDependency,
    current_user: CurrentUserDependency
):
    await service.add_message(
        chat_id=chat.id, user_id=current_user.id, role="user", content=data.query
    )

    async def event_stream():
        start_time = time.time()
        try:
            initial_state: AgentState = {
                "messages": [HumanMessage(content=data.query)],
                "current_code": "",
                "validation_error": None,
                "execution_result": None,
                "attempts": 0,
                "rag_chunks": None,
                "user_id": current_user.id,
                "chat_id": chat.id,
                "run_tests": getattr(data, 'run_test', False),
                "skip_rag": True, 
            }

            logger.info(f"Агент запущен (Skip RAG, Sandbox={initial_state['run_tests']})")
            
            final_state = await asyncio.wait_for(
                lua_agent.ainvoke(initial_state),
                timeout=60.0
            )

            generated_code = final_state.get("current_code", "")
            validation_error = final_state.get("validation_error")
            sandbox_result = final_state.get("execution_result")
            attempts = final_state.get("attempts", 0)

            yield f"data: {json.dumps({'type': 'status', 'msg': 'Код сгенерирован'}, ensure_ascii=False)}\n\n"
            
            if validation_error:
                yield f"data: {json.dumps({'type': 'status', 'msg': f'Ошибка валидации: {validation_error}'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'msg': 'Код валиден'}, ensure_ascii=False)}\n\n"

            if sandbox_result:
                if sandbox_result.success:
                    yield f"data: {json.dumps({'type': 'sandbox', 'output': sandbox_result.output}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'sandbox', 'error': sandbox_result.error}, ensure_ascii=False)}\n\n"

            clean_code = generated_code
            await service.add_message(
                chat_id=chat.id,
                user_id=current_user.id,
                role="assistant",
                content=clean_code
            )

            yield f"data: {json.dumps({
                'type': 'done',
                'code': clean_code,
                'validation_error': validation_error,
                'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
                'time_ms': int((time.time() - start_time) * 1000)
            }, ensure_ascii=False)}\n\n"

        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Таймаут агента'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")