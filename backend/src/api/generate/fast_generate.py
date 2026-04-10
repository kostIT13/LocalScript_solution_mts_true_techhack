# backend/src/api/generate/fast_endpoints.py
import asyncio
import json
import time
import logging
import re
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.services.llm.generator import stream_chat
from src.services.agent.lua_agent_graph import extract_code_block, try_fix_truncated_code
from src.services.sandbox.sandbox_service import sandbox_service, SandboxResult
from src.api.generate.dependencies import GenerationServiceDependency

router = APIRouter(prefix='/fast', tags=["Fast Generation"])
logger = logging.getLogger(__name__)


# ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────

def fix_lua_operators(code: str) -> str:
    """Заменяет запрещённые в Lua операторы на валидные."""
    # *= → = *
    code = re.sub(r'(\w+)\s*\*=\s*(.+?)(?:\n|$)', r'\1 = \1 * \2\n', code)
    # += → = +
    code = re.sub(r'(\w+)\s*\+=\s*(.+?)(?:\n|$)', r'\1 = \1 + \2\n', code)
    # -= → = -
    code = re.sub(r'(\w+)\s*-=\s*(.+?)(?:\n|$)', r'\1 = \1 - \2\n', code)
    # /= → = /
    code = re.sub(r'(\w+)\s*\/=\s*(.+?)(?:\n|$)', r'\1 = \1 / \2\n', code)
    # %= → = %
    code = re.sub(r'(\w+)\s*%=\s*(.+?)(?:\n|$)', r'\1 = \1 % \2\n', code)
    return code


def add_test_call(code: str, func_name: str, args: str = "5") -> str:
    """Добавляет тестовый вызов функции в конец кода."""
    return f"{code}\n\n-- Test call\nprint({func_name}({args}))"


# ─── СХЕМА ЗАПРОСА ────────────────────────────────────────────────────────

class FastGenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=1000, description="Задача на естественном языке")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    user_id: str = Field(default="dev-user-temp", description="ID пользователя")
    run_test: bool = Field(default=False, description="Запустить код в Sandbox")


# ─── ЭНДПОИНТ ─────────────────────────────────────────────────────────────

@router.post("/lua")
async def fast_generate_lua(req: FastGenerateRequest, service: GenerationServiceDependency):
    async def event_stream():
        start_time = time.time()
        
        # 🔹 Жёсткий системный промпт для Lua 5.4
        system_prompt = (
            "Ты генератор кода на Lua 5.4. Пиши ТОЛЬКО рабочий код. "
            "❗ В Луа НЕТ операторов *=, +=, -=, /=. Пиши 'x = x * y', а не 'x *= y'. "
            "Никаких пояснений, никакого markdown, никаких ``` блоков. Только чистый код."
        )
        prompt = f"Задача: {req.task}\n\nКод:"
        
        code = ""
        is_valid = True
        error = None
        attempts = 0
        max_attempts = 2

        # ─── ЦИКЛ ГЕНЕРАЦИИ ───
        while attempts < max_attempts:
            attempts += 1
            logger.info(f"🔄 Попытка {attempts}/{max_attempts}")
            
            # Настройки под попытку
            ctx = 1024 if attempts == 1 else 2048
            pred = 200 if attempts == 1 else 300
            
            # Если ошибка — добавляем в промпт
            if attempts > 1 and error:
                prompt += f"\n\n⚠️ ОШИБКА: {error}\n\nИСПРАВЬ КОД. ЗАКРОЙ ВСЕ БЛОКИ 'end'."
            
            # Генерация
            full_response = ""
            async for token in stream_chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=req.temperature,
                num_ctx=ctx,
                num_predict=pred
            ):
                full_response += token
                # Стримим токены только с первой попытки
                if attempts == 1:
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"

            # Очистка и фикс кода
            raw_code = extract_code_block(full_response)
            code = try_fix_truncated_code(raw_code)
            
            # Простая валидация структуры
            if 'function' in code and code.strip().endswith('end'):
                is_valid = True
                break
            else:
                error = "Incomplete code structure"

        # ─── SANDBOX (если запрошено) ───
        sandbox_result = None
        
        if req.run_test and is_valid and code.strip():
            logger.info(f"🧪 Запуск Sandbox для кода ({len(code)} символов)...")
            try:
                # 🔹 Фиксим операторы перед запуском
                test_code = fix_lua_operators(code)
                
                # 🔹 Добавляем тестовый вызов, если это функция
                match = re.search(r'function\s+(\w+)\s*\(', test_code)
                if match:
                    func_name = match.group(1)
                    test_code = add_test_call(test_code, func_name, args="5")
                    logger.info(f"🧪 Добавлен тестовый вызов: {func_name}(5)")
                
                # Запуск в Sandbox с таймаутом
                sandbox_result = await asyncio.wait_for(
                    sandbox_service.execute(test_code, timeout=5),
                    timeout=8.0
                )
                logger.info(f"✅ Sandbox: success={sandbox_result.success}")
                
            except asyncio.TimeoutError:
                sandbox_result = SandboxResult(success=False, error="Sandbox timeout (8s)")
                logger.warning("⏱ Sandbox таймаут")
            except Exception as e:
                sandbox_result = SandboxResult(success=False, error=f"Sandbox error: {str(e)}")
                logger.error(f"❌ Sandbox упал: {e}", exc_info=True)

        # ─── ФИНАЛЬНЫЙ ОТВЕТ ───
        total_ms = int((time.time() - start_time) * 1000)
        
        yield f"data: {json.dumps({
            'type': 'done',
            'code': code,
            'valid': is_valid,
            'error': error,
            'attempts': attempts,
            'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
            'timing_ms': total_ms
        }, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

        # ─── ЛОГ В БД (не блокирует стрим) ───
        try:
            if hasattr(service, 'create_generation'):
                await service.create_generation(
                    user_id=req.user_id,
                    task=req.task,
                    temperature=req.temperature,
                    context_length=1024
                )
                logger.info(f"✅ БД: запись создана")
        except Exception as e:
            logger.debug(f"ℹ️ БД пропущена (ожидаемо): {e}")

    return StreamingResponse(event_stream(), media_type="text/event-stream")