import httpx, re, asyncio, subprocess, tempfile, os
from typing import AsyncGenerator

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL = "qwen2.5-coder:1.5b"
MAX_RETRIES = 2

SYSTEM_PROMPT = """Ты — Lua-разработчик. Пиши ТОЛЬКО валидный код внутри блока ```lua.
Никаких пояснений, приветствий или комментариев вне кода.
Следуй стандартам Lua 5.1/5.4. Используй локальные переменные где возможно."""

def extract_lua(text: str) -> str:
    match = re.search(r"```lua\s*\n([\s\S]*?)\n```", text)
    return match.group(1).strip() if match else text.strip()

def validate_lua(code: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as f:
        f.write(code)
        f_path = f.name
    try:
        res = subprocess.run(["luac", "-p", f_path], capture_output=True, text=True, timeout=5)
        return res.returncode == 0, res.stderr
    finally:
        os.unlink(f_path)

async def stream_ollama(prompt: str) -> AsyncGenerator[str, None]:
    timeout = httpx.Timeout(connect=60.0, read=300.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/generate", json={
            "model": MODEL,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.3,
            "top_p": 0.9,
            "num_ctx": 4096
        }) as resp:
            async for line in resp.aiter_lines():
                if not line: continue
                chunk = line.strip()
                if chunk.startswith("data:"): chunk = chunk[5:]
                if chunk:
                    data = eval(chunk) # для простоты, в prod → json.loads
                    yield data.get("response", "")

async def generate_and_fix(task: str) -> AsyncGenerator[dict, None]:
    prompt = f"{SYSTEM_PROMPT}\n\nЗАДАЧА:\n{task}"
    buffer = ""
    
    # 1. Стриминг токенов
    async for token in stream_ollama(prompt):
        buffer += token
        yield {"type": "token", "data": token}
    
    code = extract_lua(buffer)
    
    # 2. Валидация + автокоррекция
    for attempt in range(MAX_RETRIES):
        ok, err = validate_lua(code)
        if ok:
            yield {"type": "done", "code": code, "attempts": attempt + 1}
            return
        
        # Фолбэк: просим исправить
        fix_prompt = f"{SYSTEM_PROMPT}\n\nИСХОДНАЯ ЗАДАЧА:\n{task}\n\nТВОЙ КОД:\n{code}\n\nОШИБКА luac:\n{err}\n\nИсправь и верни ТОЛЬКО ```lua блок."
        buffer = ""
        async for token in stream_ollama(fix_prompt):
            buffer += token
        code = extract_lua(buffer)
        yield {"type": "retry", "attempt": attempt + 1, "error": err}
    
    yield {"type": "failed", "code": code, "error": err, "attempts": MAX_RETRIES}