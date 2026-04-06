from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from src.api.generate.schemas import GenerateRequest
from src.api.generate.dependencies import GenerationServiceDependency
from src.services.llm.generator import stream_chat 
from src.services.llm.promts import LUA_AGENT_SYSTEM_PROMPT
import json, time


router = APIRouter(prefix='/generations', tags=["Generations"])


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
        full_code = ""
        
        try:
            prompt = f"Write Lua code for: {req.task}. ONLY code in ```lua block, no explanations."
            
            async for token in stream_chat(
                prompt=prompt,
                system_prompt=LUA_AGENT_SYSTEM_PROMPT,  
                temperature=req.temperature,
                num_ctx=req.context_length
            ):
                full_code += token
                yield f" {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
                    
            import re
            code_match = re.search(r"```lua\s*(.*?)\s*```", full_code, re.DOTALL)
            clean_code = code_match.group(1).strip() if code_match else full_code.strip()
            
            await service.update_generation(record.id, {
                "generated_code": clean_code,
                "validation_status": "success",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_completion": len(full_code.split()) 
            })
            
            yield f" {json.dumps({'type': 'done', 'code': clean_code}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            await service.update_generation(record.id, {
                "validation_status": "failed",
                "validation_log": str(e)
            })
            yield f" {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")