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
from src.api.generate.schemas import GenerateRequest


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

def _validate_lowcode_context(ctx: dict) -> tuple[bool, str]:
    if not ctx:
        return True, ""
    
    if "wf" not in ctx:
        return False, "Context must have 'wf' root key"
    
    wf = ctx["wf"]
    if not isinstance(wf, dict):
        return False, "'wf' must be an object"
    
    if "vars" not in wf and "initVariables" not in wf:
        return False, "wf must contain 'vars' or 'initVariables'"
    
    return True, ""

def _build_prompt_with_context(
    task: str, 
    context: Optional[dict], 
    history: list[dict],
    feedback: Optional[str]
) -> str:
    
    parts = []
    
    system_prompt = (
        "Ты эксперт по Lua 5.5 для платформы MWS Octapi LowCode.\n\n"
        "📦 ПРАВИЛА:\n"
        "• Все переменные схемы — в wf.vars, входные — в wf.initVariables\n"
        "• НЕ используй JsonPath — только прямое обращение: wf.vars.emails\n"
        "• Массивы: #array для длины, _utils.array.new() для создания новых\n\n"
        "📝 ФОРМАТ ОТВЕТА:\n"
        "• Если просят 'напиши функцию' → создай function name() ... end\n"
        "• Если просят 'получи/верни значение' → return выражение\n"
        "• Если работа с wf.vars/wf.initVariables → только return (без function)\n"
        "• НЕ добавляй пояснения, только код\n\n"
        "✅ ПРИМЕРЫ:\n"
        "1. 'Напиши функцию sum(a,b)' → function sum(a,b)\n  return a + b\nend\n"
        "2. 'Получи последний email' → return wf.vars.emails[#wf.vars.emails]\n"
        "3. 'Увеличь try_count_n' → return wf.vars.try_count_n + 1\n"
        "4. 'Отфильтруй по Discount' → local r=_utils.array.new(); for _,i in ipairs(wf.vars.items) do if i.Discount~=\"\" then table.insert(r,i) end end; return r"
    )
    parts.append(system_prompt)
    
    if context:
        schema_context = {}
        if "wf" in context:
            wf = context["wf"]
            if "vars" in wf:
                schema_context["wf.vars"] = wf["vars"]
            if "initVariables" in wf:
                schema_context["wf.initVariables"] = wf["initVariables"]
        
        if schema_context:
            parts.append(f"📦 КОНТЕКСТ СХЕМЫ:\n```json\n{json.dumps(schema_context, indent=2, ensure_ascii=False)}\n```")
    
    if history:
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])
        parts.append(f"💬 ИСТОРИЯ ДИАЛОГА:\n{history_text}")
    
    if feedback:
        parts.append(f"🔧 ЗАМЕЧАНИЕ: {feedback}")
    
    parts.append(f"🎯 ЗАДАЧА:\n{task}")
    
    parts.append("\n📝 ОТВЕТ: Верни Lua код согласно правилам выше. БЕЗ пояснений.")
    
    return "\n\n".join(parts)


def format_lowcode_response(code: str, output_var: str) -> dict:
    code = code.strip()
    code = re.sub(r'^```lua\s*', '', code)
    code = re.sub(r'\s*```$', '', code)
    wrapped = f"lua{{{code}}}lua"
    return {output_var: wrapped}


@router.post("/lua")
async def generate_lua(req: GenerateRequest, service: GenerationServiceDependency):
    async def event_stream():
        start_time = time.time()
        
        if req.context:
            valid, error_msg = _validate_lowcode_context(req.context)
            if not valid:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Invalid context: {error_msg}'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
        
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
        
        history = _get_session_history(req.chat_id)
        prompt = _build_prompt_with_context(
            task=req.task,
            context=req.context,
            history=history,
            feedback=req.feedback
        )
        
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
                prompt=prompt, 
                system_prompt="", 
                temperature=req.temperature, 
                num_ctx=ctx, 
                num_predict=pred
            ):
                full_response += token
                if attempts == 1:
                    yield f"data: {json.dumps({'type': 'token', 'data': token}, ensure_ascii=False)}\n\n"
            
            raw_code = extract_code_block(full_response)
            code = try_fix_truncated_code(raw_code)
            
            if 'function' in code and code.strip().endswith('end'):
                is_valid = True
                break
            elif 'return' in code:
                is_valid = True
                break
            else:
                error = "Incomplete code structure"
        
        sandbox_result = None
        if req.run_test and is_valid and code.strip():
            try:
                test_code = fix_lua_operators(code)
                
                match = re.search(r'function\s+(\w+)\s*\(([^)]*)\)', test_code)
                if match:
                    func_name = match.group(1)
                    args_str = match.group(2).strip()
                    
                    if not args_str:
                        arg_count = 0
                    else:
                        args = [a.strip() for a in args_str.split(',') if a.strip()]
                        arg_count = len(args)
                    
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
                    logger.info(f"Тестовый вызов: {func_name}({test_args})")
                
                sandbox_result = await asyncio.wait_for(
                    sandbox_service.execute(test_code, timeout=5), timeout=8.0
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
        
        formatted_response = format_lowcode_response(code, req.output_var)
        
        yield f"data: {json.dumps({
            'type': 'done',
            'code': code,  
            'formatted_response': formatted_response, 
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