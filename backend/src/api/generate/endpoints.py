from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.api.generate.schemas import GenerateRequest
from src.api.generate.dependencies import GenerationServiceDependency
import json, time


router = APIRouter()

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
            from src.services.ollama import stream_ollama_prompt
            
            async for chunk in stream_ollama_prompt(req.task):
                yield f" {json.dumps(chunk, ensure_ascii=False)}\n\n"
                if chunk.get("type") == "token":
                    full_code += chunk["data"]
                    
            await service.update_generation(record.id, {
                "generated_code": full_code,
                "validation_status": "success",
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens_completion": len(full_code.split()) 
            })
        except Exception as e:
            await service.update_generation(record.id, {
                "validation_status": "failed",
                "validation_log": str(e)
            })
            yield f" {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
