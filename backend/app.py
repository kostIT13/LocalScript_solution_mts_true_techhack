# backend/app.py
from fastapi import FastAPI, Body
from fastapi.responses import StreamingResponse
import httpx, json

app = FastAPI()

@app.post("/api/generate")
async def generate(task: str = Body(..., embed=True)):
    async def event_stream():
        timeout = 120.0  # Достаточно для загрузки модели + генерации
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                "http://ollama:11434/api/generate",
                json={
                    "model": "qwen2.5-coder:1.5b",
                    "prompt": f"Write Lua code for: {task}. ONLY code in ```lua block, no explanations.",
                    "stream": True,
                    "options": {"temperature": 0.2, "num_ctx": 4096}
                }
            ) as resp:
                full_code = ""
                
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        
                        # 1. Если есть токен кода — отдаём его
                        if "response" in chunk:
                            token = chunk["response"]
                            full_code += token
                            yield f" {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
                        
                        # 2. Если генерация завершена — отдаём финальный объект с полным кодом
                        if chunk.get("done"):
                            # Опционально: можно очистить код от ```lua ... ```
                            clean_code = full_code.strip()
                            if clean_code.startswith("```lua"):
                                clean_code = clean_code[6:]
                            if clean_code.endswith("```"):
                                clean_code = clean_code[:-3]
                            
                            yield f" {json.dumps({'type': 'done', 'code': clean_code.strip()}, ensure_ascii=False)}\n\n"
                            
                    except json.JSONDecodeError:
                        # Пропускаем битые строки (редко, но бывает)
                        continue
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")