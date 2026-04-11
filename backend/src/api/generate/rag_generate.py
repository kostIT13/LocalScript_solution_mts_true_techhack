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
from src.services.llm.generator import stream_chat
from src.services.agent.lua_agent_graph import extract_code_block, try_fix_truncated_code
from src.services.sandbox.sandbox_service import sandbox_service, SandboxResult
from src.services.rag.rag_service import rag_service, RAGChunk
from src.services.prompts.lua_rag_agent_prompt import build_rag_prompt
from src.api.generate.dependencies import GenerationServiceDependency
from src.api.generate.schemas_rag import GenerateRequest


router = APIRouter(prefix="/generate", tags=["Code Generation"])
logger = logging.getLogger(__name__)

chat_sessions: dict[str, list[dict]] = defaultdict(list)


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


def fix_lua_code(code: str) -> str:
    """
    🔹 Исправляет распространённые ошибки в сгенерированном коде:
    - Удаляет markdown блоки (```lua ... ```)
    - Удаляет лишние 'end' в конце
    - Добавляет недостающие 'end' для закрытия блоков
    """
    # 1. Удаляем markdown блоки
    code = re.sub(r'^```lua\s*', '', code, flags=re.MULTILINE)
    code = re.sub(r'^```\s*', '', code, flags=re.MULTILINE)
    code = re.sub(r'\s*```$', '', code, flags=re.MULTILINE)
    code = code.strip()
    
    if not code:
        return code
    
    # 2. Считаем открывающие и закрывающие блоки
    # Открывающие: function, if, for, while, repeat
    opens = (
        len(re.findall(r'\bfunction\b', code)) +
        len(re.findall(r'\bif\b', code)) +
        len(re.findall(r'\bfor\b', code)) +
        len(re.findall(r'\bwhile\b', code)) +
        len(re.findall(r'\brepeat\b', code))
    )
    
    # Закрывающие: end, until
    closes = (
        len(re.findall(r'\bend\b', code)) +
        len(re.findall(r'\buntil\b', code))
    )
    
    # 3. Удаляем лишние 'end' в конце (если нет соответствующих открывающих)
    while closes > opens and code.rstrip().endswith('end'):
        # Удаляем последний 'end' с возможными пробелами/переносами
        code = re.sub(r'\s*end\s*$', '', code).strip()
        closes -= 1
    
    # 4. Добавляем недостающие 'end'
    while opens > closes:
        code = code.rstrip() + '\nend'
        closes += 1
    
    return code.strip()


def _should_use_rag(query: str, use_rag: Optional[bool]) -> bool:
    """
    🔹 Для хакатона: ВСЕГДА ищем в базе, кроме явного use_rag=False.
    ChromaDB работает за ~0.1-0.3с, оверхед минимален.
    """
    if use_rag is False:
        return False
    if use_rag is True:
        return True
    return True 


@router.post("/lua_rag")
async def generate_lua_with_rag(req: GenerateRequest, service: GenerationServiceDependency):
    async def event_stream():
        start_time = time.time()
        
        rag_chunks: list[RAGChunk] = []
        use_rag_flag = _should_use_rag(req.task, req.use_rag)
        
        if use_rag_flag:
            try:
                rag_chunks = await rag_service.search(
                    query=req.task, user_id=req.user_id, top_k=3
                )
                logger.info(f"RAG: найдено {len(rag_chunks)} чанков")
            except Exception as e:
                logger.warning(f"RAG error: {e}")
                rag_chunks = [] 
        
        # 🔹 Усиленный системный промпт
        system_prompt = (
            "Ты эксперт по Lua 5.4. Пиши ТОЛЬКО рабочий, завершённый код.\n"
            "КРИТИЧЕСКИ ВАЖНО:\n"
            "1. Если пишешь функцию — ВСЕГДА закрывай 'end'\n"
            "2. НЕ добавляй 'end' если нет function/if/for/while/repeat\n"
            "3. Код должен быть ПОЛНОСТЬЮ завершён, не обрывай на полуслове\n"
            "4. Не используй markdown блоки (```lua ... ```)\n"
            "5. Пиши только код, без пояснений и комментариев про задачу\n"
            "ПРАВИЛА: Вместо 'x *= y' пиши 'x = x * y'.\n"
            "Проверяй типы аргументов, если задача подразумевает валидацию.\n"
        )
        
        history = _get_session_history(req.chat_id)
        
        rag_context = ""
        if rag_chunks:
            rag_context = "\n\nРЕЛЕВАНТНЫЕ ФРАГМЕНТЫ ИЗ ДОКУМЕНТАЦИИ:\n" + "\n---\n".join([
                f"[{i+1}] {chunk.filename}:\n{chunk.content[:300]}..." 
                for i, chunk in enumerate(rag_chunks)
            ])
        
        if req.feedback and history:
            last_code = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
            prompt = f"Исходный код:\n{last_code}\n\nЗАМЕЧАНИЕ: {req.feedback}\n\nИСПРАВЬ код. Задача: {req.task}"
        else:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])
            base_prompt = f"{history_text}\n\nЗадача: {req.task}" if history_text else f"Задача: {req.task}"
            prompt = f"{base_prompt}{rag_context}\n\nКод:"
        
        code = ""
        is_valid = True
        error = None
        attempts = 0
        max_attempts = 2
        
        while attempts < max_attempts:
            attempts += 1
            ctx = 4096 if attempts == 1 else 2048
            # 🔹 Увеличил num_predict для более длинных ответов
            pred = 512 if attempts == 1 else 600
            
            if attempts > 1 and error:
                prompt += f"\n\nОШИБКА: {error}\nИСПРАВЬ И ЗАКРОЙ ВСЕ БЛОКИ."
            
            full_response = ""
            async for token in stream_chat(
                prompt=prompt, system_prompt=system_prompt,
                temperature=req.temperature, num_ctx=ctx, num_predict=pred
            ):
                full_response += token
                if attempts == 1:
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
            
            # 🔹 Извлекаем и чистим код
            raw_code = extract_code_block(full_response)
            code = fix_lua_code(raw_code)  # ← ← ← Используем новый фиксер
            logger.info(f"🔧 Код после фиксации: {len(code)} символов")
            
            # 🔹 Улучшенная валидация
            code_stripped = code.strip()
            
            if not code_stripped:
                is_valid = False
                error = "Empty code"
            elif 'function' in code_stripped or 'if ' in code_stripped or 'for ' in code_stripped or 'while ' in code_stripped:
                # Есть блоки — проверяем баланс
                opens = (
                    len(re.findall(r'\bfunction\b', code_stripped)) +
                    len(re.findall(r'\bif\b', code_stripped)) +
                    len(re.findall(r'\bfor\b', code_stripped)) +
                    len(re.findall(r'\bwhile\b', code_stripped)) +
                    len(re.findall(r'\brepeat\b', code_stripped))
                )
                closes = (
                    len(re.findall(r'\bend\b', code_stripped)) +
                    len(re.findall(r'\buntil\b', code_stripped))
                )
                
                if opens == closes:
                    is_valid = True
                    error = None
                else:
                    is_valid = False
                    error = f"Mismatched blocks: {opens} opens, {closes} closes"
            else:
                # Просто код без блоков — валидно
                is_valid = True
                error = None
            
            if is_valid:
                break
        
        # 🔹 Sandbox с улучшенной логикой
        sandbox_result = None
        if req.run_test and is_valid and code.strip():
            try:
                test_code = fix_lua_operators(code)
                
                # 🔹 Проверяем, есть ли функция для вызова
                match = re.search(r'function\s+(\w+)\s*\(([^)]*)\)', test_code)
                
                if match:
                    # Есть функция — вызываем её
                    func_name = match.group(1)
                    args_str = match.group(2).strip()
                    
                    # Считаем аргументы
                    if not args_str:
                        arg_count = 0
                    else:
                        args = [a.strip() for a in args_str.split(',') if a.strip()]
                        arg_count = len(args)
                    
                    # Генерируем тестовые аргументы
                    if arg_count == 0:
                        test_args = ""
                    elif arg_count == 1:
                        test_args = "5"
                    elif arg_count == 2:
                        test_args = "2, 3"
                    elif arg_count == 3:
                        test_args = "1, 2, 3"
                    else:
                        test_args = ", ".join(str(i) for i in range(1, arg_count + 1))
                    
                    test_code = f"{test_code}\n\nprint({func_name}({test_args}))"
                    logger.info(f"🧪 Тестовый вызов функции: {func_name}({test_args})")
                else:
                    # Нет функции — просто проверяем синтаксис
                    logger.info("🧪 Нет функции для вызова, проверяю синтаксис...")
                    test_code = f"{test_code}\n\n-- syntax check ok"
                
                sandbox_result = await asyncio.wait_for(
                    sandbox_service.execute(test_code, timeout=5), timeout=8.0
                )
                
                # 🔹 Если ошибка компиляции — пробуем исправить
                if not sandbox_result.success and 'expected near' in str(sandbox_result.error):
                    logger.warning(f"⚠️ Ошибка синтаксиса, пробую исправить...")
                    fixed_code = fix_lua_code(code)
                    if fixed_code != code:
                        sandbox_result = await asyncio.wait_for(
                            sandbox_service.execute(fixed_code, timeout=5), timeout=8.0
                        )
                
            except Exception as e:
                logger.warning(f"Тест упал: {e}. Пробую без print()...")
                try:
                    fallback_code = fix_lua_operators(code) + "\n\n-- syntax check ok"
                    sandbox_result = await asyncio.wait_for(
                        sandbox_service.execute(fallback_code, timeout=3), timeout=5.0
                    )
                except Exception as e2:
                    sandbox_result = SandboxResult(success=False, error=f"Sandbox error: {str(e2)}")
        
        total_ms = int((time.time() - start_time) * 1000)
        session_id = req.chat_id or str(uuid.uuid4())
        
        if session_id:
            _save_to_session(session_id, "user", req.task)
            _save_to_session(session_id, "assistant", code)
        
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
                logger.info(f"БД: сохранено {record.id}")
        except Exception as e:
            logger.warning(f"БД: пропуск ({e})")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")