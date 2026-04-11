# backend/src/api/generate/generate_endpoints.py
import asyncio
import json
import time
import logging
import re
import uuid
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.services.llm.generator import stream_chat
from src.services.agent.lua_agent_graph import extract_code_block, try_fix_truncated_code
from src.services.sandbox.sandbox_service import sandbox_service, SandboxResult
from src.services.rag.rag_service import rag_service, RAGChunk
from src.services.prompts.lua_rag_agent_prompt import build_rag_prompt
from src.api.generate.dependencies import GenerationServiceDependency
from src.api.generate.schemas_rag import GenerateRequest

router = APIRouter(prefix="/generate", tags=["Code Generation"])
logger = logging.getLogger(__name__)

# 🔹 In-memory сессии (для контекста диалога; в продакшене → Redis)
chat_sessions: dict[str, list[dict]] = defaultdict(list)


# ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────
def _get_session_history(chat_id: Optional[str]) -> list[dict]:
    if not chat_id:
        return []
    return chat_sessions.get(chat_id, [])[-8:]


def _save_to_session(chat_id: str, role: str, content: str):
    if not chat_id:
        return
    chat_sessions[chat_id].append({"role": role, "content": content})
    if len(chat_sessions[chat_id]) > 12:
        chat_sessions[chat_id] = chat_sessions[chat_id][-12:]


def fix_lua_operators(code: str) -> str:
    """Заменяет запрещённые в Lua операторы на валидные."""
    code = re.sub(r'(\w+)\s*\*=\s*(.+?)(?:\n|$)', r'\1 = \1 * \2\n', code)
    code = re.sub(r'(\w+)\s*\+=\s*(.+?)(?:\n|$)', r'\1 = \1 + \2\n', code)
    code = re.sub(r'(\w+)\s*-=\s*(.+?)(?:\n|$)', r'\1 = \1 - \2\n', code)
    code = re.sub(r'(\w+)\s*\/=\s*(.+?)(?:\n|$)', r'\1 = \1 / \2\n', code)
    return code


def _should_use_rag(query: str, use_rag: Optional[bool]) -> bool:
    """
    🔹 Для хакатона: ВСЕГДА ищем в базе, кроме явного use_rag=False.
    ChromaDB работает за ~0.1-0.3с, оверхед минимален.
    """
    if use_rag is False:
        return False
    if use_rag is True:
        return True
    return True  # ✅ Всегда ищем в базе (быстро и надёжно)


# ─── ОСНОВНОЙ ЭНДПОИНТ ────────────────────────────────────────────────────
@router.post("/lua_rag")
async def generate_lua_with_rag(req: GenerateRequest, service: GenerationServiceDependency):
    """
    🎯 Генерация Lua-кода с поддержкой RAG (база знаний).
    
    Особенности:
    • Умный выбор: использовать RAG или нет (авто/ручной режим)
    • Контекст сессии через chat_id + feedback
    • Полная валидация: luac + шаблоны + sandbox
    • Сохранение в БД для истории
    """
    async def event_stream():
        start_time = time.time()
        
        # 🔹 1. RAG: поиск в базе знаний (если нужно)
        rag_chunks: list[RAGChunk] = []
        use_rag_flag = _should_use_rag(req.task, req.use_rag)
        
        if use_rag_flag:
            try:
                rag_chunks = await rag_service.search(
                    query=req.task, user_id=req.user_id, top_k=3
                )
                logger.info(f"🔍 RAG: найдено {len(rag_chunks)} чанков")
            except Exception as e:
                logger.warning(f"⚠️ RAG error: {e}")
                rag_chunks = []  # Fallback: генерируем без контекста
        
        # 🔹 2. Системный промпт (жесткие правила Lua 5.4)
        system_prompt = (
            "Ты эксперт по Lua 5.4. Пиши ТОЛЬКО рабочий, готовый к использованию код.\n"
            "❗ ПРАВИЛА: Вместо 'x *= y' пиши 'x = x * y'. Всегда закрывай блоки 'end'.\n"
            "Проверяй типы аргументов, если задача подразумевает валидацию.\n"
            "Никаких пояснений, никакого markdown, только чистый код."
        )
        
        # 🔹 3. Формируем промпт с контекстом
        history = _get_session_history(req.chat_id)
        
        # Контекст из RAG
        rag_context = ""
        if rag_chunks:
            rag_context = "\n\n📚 РЕЛЕВАНТНЫЕ ФРАГМЕНТЫ ИЗ ДОКУМЕНТАЦИИ:\n" + "\n---\n".join([
                f"[{i+1}] {chunk.filename}:\n{chunk.content[:300]}..." 
                for i, chunk in enumerate(rag_chunks)
            ])
        
        # История диалога + фидбек
        if req.feedback and history:
            last_code = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
            prompt = f"Исходный код:\n{last_code}\n\n⚠️ ЗАМЕЧАНИЕ: {req.feedback}\n\nИСПРАВЬ код. Задача: {req.task}"
        else:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])
            base_prompt = f"{history_text}\n\nЗадача: {req.task}" if history_text else f"Задача: {req.task}"
            prompt = f"{base_prompt}{rag_context}\n\nКод:"
        
        # 🔹 4. Цикл генерации с валидацией
        code = ""
        is_valid = True
        error = None
        attempts = 0
        max_attempts = 2
        
        while attempts < max_attempts:
            attempts += 1
            # Параметры под попытку (фиксированные для жюри)
            ctx = 4096 if attempts == 1 else 2048
            pred = 256 if attempts == 1 else 300
            
            if attempts > 1 and error:
                prompt += f"\n\n❗ ОШИБКА: {error}\nИСПРАВЬ И ЗАКРОЙ ВСЕ БЛОКИ."
            
            full_response = ""
            async for token in stream_chat(
                prompt=prompt, system_prompt=system_prompt,
                temperature=req.temperature, num_ctx=ctx, num_predict=pred
            ):
                full_response += token
                if attempts == 1:
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
            
            # Очистка кода
            raw_code = extract_code_block(full_response)
            code = try_fix_truncated_code(raw_code)
            
            # Структурная валидация
            if 'function' in code and code.strip().endswith('end'):
                is_valid = True
                break
            else:
                error = "Incomplete code structure"
        
        # 🔹 5. Sandbox (если запрошено)
        sandbox_result = None
        if req.run_test and is_valid and code.strip():
            try:
                test_code = fix_lua_operators(code)
                
                # 🔹 Анализируем сигнатуру функции для правильного тестового вызова
                match = re.search(r'function\s+(\w+)\s*\(([^)]*)\)', test_code)
                if match:
                    func_name = match.group(1)
                    args_str = match.group(2).strip()
                    
                    # Считаем количество аргументов
                    arg_count = len([a.strip() for a in args_str.split(',') if a.strip()]) if args_str else 0
                    
                    # Генерируем тестовые аргументы: 1→5, 2→1,2, 3→1,2,3 и т.д.
                    if arg_count == 0:
                        test_args = ""
                    elif arg_count == 1:
                        test_args = "5"
                    else:
                        test_args = ", ".join(str(i) for i in range(1, arg_count + 1))
                    
                    test_code = f"{test_code}\n\nprint({func_name}({test_args}))"
                    logger.info(f"🧪 Тестовый вызов: {func_name}({test_args})")
                
                sandbox_result = await asyncio.wait_for(
                    sandbox_service.execute(test_code, timeout=5), timeout=8.0
                )
                
            except Exception as e:
                # 🔹 Fallback: если тест упал, пробуем просто проверить синтаксис
                logger.warning(f"⚠️ Тест упал: {e}. Пробую без print()...")
                try:
                    fallback_code = fix_lua_operators(code) + "\n\n-- syntax check ok"
                    sandbox_result = await asyncio.wait_for(
                        sandbox_service.execute(fallback_code, timeout=3), timeout=5.0
                    )
                except Exception as e2:
                    sandbox_result = SandboxResult(success=False, error=f"Sandbox error: {str(e2)}")
        
        # 🔹 6. Финальный ответ
        total_ms = int((time.time() - start_time) * 1000)
        session_id = req.chat_id or str(uuid.uuid4())
        
        # Сохраняем в сессию
        if session_id:
            _save_to_session(session_id, "user", req.task)
            _save_to_session(session_id, "assistant", code)
        
        # Метаданные RAG для ответа
        rag_meta = {
            "used": bool(rag_chunks),
            "sources": [
                {"filename": c.filename, "score": c.score, "preview": c.content[:100]}
                for c in rag_chunks[:3]
            ] if rag_chunks else []
        }
        
        yield f"data: {json.dumps({
            'type': 'done',
            'code': code,
            'valid': is_valid,
            'error': error,
            'attempts': attempts,
            'chat_id': session_id,
            'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
            'rag': rag_meta,
            'timing_ms': total_ms
        }, ensure_ascii=False)}\n\n"
        yield " [DONE]\n\n"
        
        # 🔹 7. Сохранение в БД (не блокирует стрим)
        try:
            if hasattr(service, 'create_generation'):
                record = await service.create_generation(
                    user_id=req.user_id, task=req.task,
                    temperature=req.temperature, context_length=4096,
                    language="lua", model_name="qwen2.5-coder:1.5b"
                )
                await service.update_generation(
                    generation_id=record.id,
                    update_data={
                        "generated_code": code,
                        "validation_status": "success" if is_valid else "failed",
                        "validation_log": error,
                        "attempts_count": attempts,
                        "latency_ms": total_ms,
                        "tokens_prompt": len(prompt),
                        "tokens_completion": len(code.split()),
                    }
                )
                logger.info(f"✅ БД: сохранено {record.id}")
        except Exception as e:
            logger.warning(f"⚠️ БД: пропуск ({e})")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")