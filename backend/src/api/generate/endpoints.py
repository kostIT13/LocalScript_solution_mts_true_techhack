# backend/src/api/generate/endpoints.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.api.generate.schemas import GenerateRequest
from src.api.generate.dependencies import GenerationServiceDependency
from src.services.sandbox.sandbox_service import SandboxService, SandboxResult
from src.services.agent.lua_agent_graph import lua_agent, AgentState  
from langchain_core.messages import HumanMessage  
import json, time, logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/generations', tags=["Generations"])

sandbox_service = SandboxService(image_name="localscript-sandbox")


@router.post("/generate", status_code=201)
async def generate_code(
    req: GenerateRequest,               
    service: GenerationServiceDependency,
    user_id: str = "dev-user-temp"     
):
    record = await service.create_generation(
        user_id=user_id,
        task=req.task,
        temperature=req.temperature,
        context_length=req.context_length
    )
 
    async def event_stream():
        start_time = time.time()
        
        try:
            initial_state: AgentState = {
                "messages": [HumanMessage(content=req.task)],  
                "current_code": "",
                "validation_error": None,
                "attempts": 0,
                "rag_context": None,
                "user_id": user_id,
                "chat_id": None
            }

            logger.info("Запуск Lua агента...")
            final_state = await lua_agent.ainvoke(initial_state)
            
            generated_code = final_state.get("current_code", "")
            validation_error = final_state.get("validation_error")
            attempts = final_state.get("attempts", 0)
            rag_context = final_state.get("rag_context")
            
            if generated_code:
                for char in generated_code:
                    yield f"data: {json.dumps({'type': 'token', 'data': char}, ensure_ascii=False)}\n\n"
            
            sandbox_result = None
            if req.run_test and generated_code and not validation_error:
                logger.info(f"Запуск Sandbox (попытка #{attempts})...")
                
                sandbox_result: SandboxResult = sandbox_service.execute(
                    code=generated_code,
                    timeout=5
                )
                
                yield f" {json.dumps({'type': 'sandbox_start'}, ensure_ascii=False)}\n\n"
            
            update_data = {
                "generated_code": generated_code,
                "validation_status": "failed" if validation_error else "success",
                "validation_log": validation_error,
                "attempts_count": attempts,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_completion": len(generated_code.split()) if generated_code else 0
            }
            
            if sandbox_result:
                update_data["sandbox_output"] = sandbox_result.output
                update_data["sandbox_error"] = sandbox_result.error
                update_data["sandbox_success"] = sandbox_result.success
            
            await service.update_generation(record.id, update_data)
            
            # 8. Финальный SSE-ответ
            final_payload = {
                "type": "done",
                "code": generated_code,
                "sandbox_result": sandbox_result.model_dump() if sandbox_result else None,
                "agent_attempts": attempts,
                "used_rag": bool(rag_context)
            }
            yield f" {json.dumps(final_payload, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"Critical error in agent flow: {e}", exc_info=True)
            
            await service.update_generation(record.id, {
                "validation_status": "failed",
                "validation_log": str(e)
            })
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")