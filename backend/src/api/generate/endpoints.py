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
from src.api.generate.dependencies import GenerationServiceDependency


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
    code = re.sub(r'(\w+)\s*\*=\s*(.+?)(?:\n|$)', r'\1 = \1 * \2\n', code)
    code = re.sub(r'(\w+)\s*\+=\s*(.+?)(?:\n|$)', r'\1 = \1 + \2\n', code)
    code = re.sub(r'(\w+)\s*-=\s*(.+?)(?:\n|$)', r'\1 = \1 - \2\n', code)
    code = re.sub(r'(\w+)\s*\/=\s*(.+?)(?:\n|$)', r'\1 = \1 / \2\n', code)
    return code

def _needs_clarification(task: str) -> Optional[str]:
    task_lower = task.lower().strip()
    
    if len(task.split()) < 4:
        return "Уточните: какие входные параметры и что должна возвращать функция?"
    
    vague_patterns = [
        r'^напиши функцию$',
        r'^сделай [а-я]+$',
        r'^работ[а-я]+ с таблиц', 
        r'^как [а-я]+$',           
        r'^function\s*$',         
        r'^lua\s*$',               
        r'^test$',                 
        r'^помоги$',              
    ]
    if any(re.search(p, task_lower) for p in vague_patterns):
        return "Уточните задачу: что именно должна делать функция? Какие аргументы и возврат?"
    
    if 'таблиц' in task_lower and not any(kw in task_lower for kw in ['insert', 'remove', 'sort', 'find', 'встав', 'удал', 'сортир', 'поиск']):
        return "Уточните: вы хотите вставку, удаление, сортировку или поиск в таблице?"
    
    return None

class GenerateRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=1000, description="Задача на естественном языке")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    user_id: str = Field(default="dev-user-temp")
    run_test: bool = Field(default=False, description="Запустить код в Sandbox")
    chat_id: Optional[str] = Field(default=None, description="ID сессии для продолжения диалога")
    feedback: Optional[str] = Field(default=None, description="Обратная связь для улучшения кода")

@router.post("/lua")
async def generate_lua(req: GenerateRequest, service: GenerationServiceDependency):
    """
    🎯 Генерация Lua-кода (простой режим без RAG).
    
    Особенности:
    • Уточняющие вопросы для неясных задач
    • Контекст сессии через chat_id + feedback
    • Умный тестовый вызов с правильным числом аргументов
    • Сохранение в БД для истории
    """
    async def event_stream():
        start_time = time.time()
        
        clarification = _needs_clarification(req.task)
        
        if clarification and not req.chat_id:
            session_id = str(uuid.uuid4())  
            logger.info(f"Запрос неясен, задаю вопрос: '{req.task[:50]}...'")
            
            yield f"data: {json.dumps({
                'type': 'clarification',
                'question': clarification,
                'chat_id': session_id,
                'suggestion': "Попробуйте: 'Напиши функцию sum(a, b) возвращающую a+b'"
            }, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return 
        
        system_prompt = (
            "Ты эксперт по Lua 5.4. Пиши ТОЛЬКО рабочий, готовый к использованию код.\n"
            "ПРАВИЛА:\n"
            "• Вместо 'x *= y' пиши 'x = x * y'\n"
            "• Всегда закрывай блоки 'end'\n"
            "• Для валидации аргументов используй 'return nil, \"ошибка\"' вместо 'error()'\n"
            "• Проверяй типы аргументов, если задача подразумевает валидацию\n"
            "Никаких пояснений, никакого markdown, только чистый код."
        )
        
        history = _get_session_history(req.chat_id)
        
        if req.feedback and history:
            last_code = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
            prompt = f"Исходный код:\n{last_code}\n\nЗАМЕЧАНИЕ: {req.feedback}\n\nИСПРАВЬ код. Задача: {req.task}"
        else:
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])
            prompt = f"{history_text}\n\nЗадача: {req.task}\n\nКод:" if history_text else f"Задача: {req.task}\n\nКод:"
        
        code = ""
        is_valid = True
        error = None
        attempts = 0
        max_attempts = 2
        
        while attempts < max_attempts:
            attempts += 1
            ctx = 4096 if attempts == 1 else 2048
            pred = 256 if attempts == 1 else 300
            
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
            
            raw_code = extract_code_block(full_response)
            code = try_fix_truncated_code(raw_code)
            
            if 'function' in code and code.strip().endswith('end'):
                is_valid = True
                break
            else:
                error = "Incomplete code structure"
        
        # 🔹 5. Sandbox (если запрошено) — ИСПРАВЛЕНО
        sandbox_result = None
        if req.run_test and is_valid and code.strip():
            try:
                test_code = fix_lua_operators(code)
                
                # 🔹 Умный тестовый вызов: анализируем сигнатуру функции
                match = re.search(r'function\s+(\w+)\s*\(([^)]*)\)', test_code)
                if match:
                    func_name = match.group(1)
                    args_str = match.group(2).strip()
                    
                    # Считаем количество аргументов
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
        
        total_ms = int((time.time() - start_time) * 1000)
        session_id = req.chat_id or str(uuid.uuid4())
        
        if session_id:
            _save_to_session(session_id, "user", req.task)
            _save_to_session(session_id, "assistant", code)
        
        yield f"data: {json.dumps({
            'type': 'done',
            'code': code,
            'valid': is_valid,
            'error': error,
            'attempts': attempts,
            'chat_id': session_id,
            'sandbox_result': sandbox_result.model_dump() if sandbox_result else None,
            'timing_ms': total_ms
        }, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
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
                    }
                )
                logger.info(f"БД: сохранено {record.id}")
        except Exception as e:
            logger.warning(f"БД: пропуск ({e})")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")