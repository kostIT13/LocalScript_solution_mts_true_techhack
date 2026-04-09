import asyncio
import json
import time
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from src.api.generate.schemas import GenerateRequest
from src.api.generate.dependencies import GenerationServiceDependency
from src.services.sandbox.sandbox_service import sandbox_service, SandboxResult
from src.services.agent.lua_agent_graph import lua_agent, AgentState

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/generations', tags=["Generations"])


@router.post("/generate", status_code=200)
async def generate_code(
    req: GenerateRequest,
    service: GenerationServiceDependency,
    user_id: str = "dev-user-temp"
):
    record = await asyncio.wait_for(
        service.create_generation(user_id=user_id, task=req.task, temperature=req.temperature, context_length=req.context_length),
        timeout=5.0
    )

    async def event_stream():
        start_time = time.time()
        try:
            initial_state: AgentState = {
                "messages": [HumanMessage(content=req.task)],
                "current_code": "",
                "validation_error": None,
                "execution_result": None,
                "attempts": 0,
                "rag_chunks": None,
                "user_id": user_id,
                "chat_id": None,
                "run_tests": req.run_test,
            }

            logger.info(f"[T+{time.time()-start_time:.1f}s] Запуск агента...")
            final_state = await asyncio.wait_for(
                lua_agent.ainvoke(initial_state),
                timeout=120.0
            )

            generated_code = final_state.get("current_code", "")
            validation_error = final_state.get("validation_error")
            attempts = final_state.get("attempts", 0)
            rag_chunks = final_state.get("rag_chunks")
            execution_result = final_state.get("execution_result")

            logger.info(f"[T+{time.time()-start_time:.1f}s] Агент готов. Код: {bool(generated_code)}, Попытки: {attempts}")

            if generated_code:
                chunk_size = 150
                for i in range(0, len(generated_code), chunk_size):
                    yield f"data: {json.dumps({'type': 'code_chunk', 'data': generated_code[i:i+chunk_size]}, ensure_ascii=False)}\n\n"

            sandbox_result: SandboxResult | None = execution_result
            if req.run_test and generated_code and not validation_error and not sandbox_result:
                logger.info(f"[T+{time.time()-start_time:.1f}s] Запуск Sandbox...")
                try:
                    sandbox_result = await asyncio.wait_for(
                        sandbox_service.execute(code=generated_code, timeout=5),
                        timeout=10.0 
                    )
                except asyncio.TimeoutError:
                    sandbox_result = SandboxResult(success=False, error="Sandbox timeout (10s)")
                logger.info(f"[T+{time.time()-start_time:.1f}s] Sandbox завершён: success={sandbox_result.success}")

            update_data = {
                "generated_code": generated_code,
                "validation_status": "failed" if validation_error else "success",
                "validation_log": validation_error,
                "attempts_count": attempts,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_completion": len(generated_code.split()),
            }
            if sandbox_result:
                update_data.update({
                    "sandbox_output": sandbox_result.output,
                    "sandbox_error": sandbox_result.error,
                    "sandbox_success": sandbox_result.success,
                })

            await asyncio.wait_for(service.update_generation(record.id, update_data), timeout=5.0)

            yield f"data: {json.dumps({
                'type': 'done',
                'code': generated_code,
                'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
                'agent_attempts': attempts,
                'used_rag': bool(rag_chunks),
                'total_time_ms': int((time.time() - start_time) * 1000)
            }, ensure_ascii=False)}\n\n"

        except asyncio.TimeoutError:
            logger.error("Превышено время выполнения агента (120s)")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Генерация заняла слишком много времени. Попробуйте упростить запрос.'})}\n\n"
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'Внутренняя ошибка: {str(e)}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")