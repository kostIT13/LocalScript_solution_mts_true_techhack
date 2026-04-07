# backend/src/api/generate/endpoints.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.api.generate.schemas import GenerateRequest
from src.api.generate.dependencies import GenerationServiceDependency
from src.services.llm.generator import stream_chat 
from src.services.prompts.lua_agent_system_prompt import LUA_AGENT_SYSTEM_PROMPT  
from src.services.sandbox.sandbox_service import SandboxService, SandboxResult  
import json
import time
import re
import logging


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
        full_response = ""  
        
        try:
            prompt = f"Task: {req.task}\n\nWrite ONLY valid Lua code. Return code in ```lua ... ``` block. No explanations, no markdown outside the code block."
            
            async for token in stream_chat(
                prompt=prompt,
                system_prompt=LUA_AGENT_SYSTEM_PROMPT,  
                temperature=req.temperature,
                num_ctx=req.context_length
            ):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
                    
            code_match = re.search(r"```lua\s*(.*?)\s*```", full_response, re.DOTALL)
            clean_code = code_match.group(1).strip() if code_match else full_response.strip()
            
            sandbox_result = None
            if req.run_test and clean_code:
                logger.info(f"Запускаю Sandbox для кода: {clean_code[:100]}...")
                
                sandbox_result: SandboxResult = sandbox_service.execute(
                    code=clean_code,
                    timeout=5  
                )
                
                yield f"data: {json.dumps({'type': 'sandbox_start'}, ensure_ascii=False)}\n\n"
            
            update_data = {
                "generated_code": clean_code,
                "validation_status": "success",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_completion": len(full_response.split())
            }
            if sandbox_result:
                update_data["sandbox_output"] = sandbox_result.output
                update_data["sandbox_error"] = sandbox_result.error
                update_data["sandbox_success"] = sandbox_result.success
            
            await service.update_generation(record.id, update_data)
            
            final_payload = {
                "type": "done",
                "code": clean_code,
                "sandbox_result": sandbox_result.model_dump() if sandbox_result else None
            }
            yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            
            await service.update_generation(record.id, {
                "validation_status": "failed",
                "validation_log": str(e)
            })
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")