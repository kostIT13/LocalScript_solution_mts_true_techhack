import httpx
import json
from src.core.config import settings

async def stream_ollama_prompt(task: str, temperature: float = 0.2, context_length: int = 4096):
    """
    Стримит ответ от Ollama. Возвращает словари, которые роутер превратит в SSE.
    yield: {"type": "token", "data": "..."}
    yield: {"type": "done", "code": "..."}
    """
    prompt = f"Write Lua code for: {task}. ONLY code in ```lua block, no explanations."
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_HOST}/api/generate",
            json={
                "model": settings.OLLAMA_LLM_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": temperature, "num_ctx": context_length}
            }
        ) as resp:
            full_code = ""
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    
                    # 1. Отдаём токен
                    if "response" in chunk:
                        token = chunk["response"]
                        full_code += token
                        yield {"type": "token", "data": token}
                        
                    # 2. Генерация завершена → отдаём чистый код
                    if chunk.get("done"):
                        clean_code = full_code.strip()
                        if clean_code.startswith("```lua"):
                            clean_code = clean_code[6:]
                        if clean_code.endswith("```"):
                            clean_code = clean_code[:-3]
                            
                        yield {"type": "done", "code": clean_code.strip()}
                        
                except json.JSONDecodeError:
                    continue