import re
import asyncio
import logging
from typing import TypedDict, Annotated, List, Optional, Literal, Tuple
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from src.services.llm.generator import stream_chat
from src.services.prompts.lua_rag_agent_prompt import build_rag_prompt
from src.services.rag.rag_service import RAGChunk, rag_service
from src.services.sandbox.sandbox_service import sandbox_service, SandboxResult

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_code: str
    validation_error: Optional[str]
    execution_result: Optional[SandboxResult]
    attempts: int
    rag_chunks: Optional[List[RAGChunk]]
    user_id: str
    chat_id: Optional[str]
    run_tests: bool
    skip_rag: bool
    needs_clarification: bool
    fast_mode: bool



def extract_code_block(text: str) -> str:
    if not text:
        return ""
    
    parts = text.split("```")
    if len(parts) >= 3:
        code_block = parts[1]
        first_line = code_block.split('\n')[0].strip().lower()
        if first_line in ('lua', 'python', 'javascript', 'js', 'typescript', 'ts'):
            code_block = '\n'.join(code_block.split('\n')[1:])
    else:
        code_block = text
        
    lines = code_block.split('\n')
    clean_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        if re.match(r'^[а-яА-Я]', stripped) or re.match(r'^(This|The|Example|Parameters|Usage|Note|Пример)', stripped, re.IGNORECASE):
            break
            
        clean_lines.append(line)
        
    code = '\n'.join(clean_lines).strip()
    if not code:
        return ""
        
    opens = len(re.findall(r'\b(function|if|while|for|repeat)\b', code))
    closes = len(re.findall(r'\bend\b', code))
    if opens > closes:
        code += '\n' + 'end\n' * (opens - closes)
        
    return code


def try_fix_truncated_code(code: str) -> str:
    if not code or code.strip().endswith('end'):
        return code
    if not any(code.strip().endswith(kw) for kw in ['end', 'then', 'do', 'else', ')', '"', "'"]):
        return code + "\nend"
    return code


def _clean_lua_code(code: str) -> str:
    if not code:
        return ""
    
    code = re.sub(r'\[Источник:[^\]]*\]\s*', '', code)
    code = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', code)
    
    garbage_phrases = [
        r'Не найдено релевантных фрагментов\.?$',
        r'ДОКУМЕНТАЦИЯ:.*$',
        r'КОНТЕКСТ:.*$',
        r'Пользователь:.*$',
        r'Ассистент:.*$',
        r'ЗАПРОС:.*$',
        r'Твой ответ:.*$',
        r'No relevant fragments found\.?$',
        r'DOCUMENTATION:.*$',
        r'CONTEXT:.*$',
        r'User:.*$',
        r'Assistant:.*$',
    ]
    for phrase in garbage_phrases:
        code = re.sub(phrase, '', code, flags=re.MULTILINE | re.IGNORECASE)
    
    lines = code.split('\n')
    cleaned = []
    in_code_block = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped and not cleaned:
            continue
        if in_code_block and stripped and not stripped.startswith('--') and not re.match(r'^[\s\w\(\)\{\}\[\]=,;:+\-*\/%<>&|!^~\.]+$', stripped):
            break
        if re.match(r'^(local\s+)?function\s+\w+', stripped):
            in_code_block = True
        if stripped.startswith('--') and 'return' in stripped and 'function' not in stripped:
            stripped = stripped.lstrip('-').strip()
            if stripped:
                cleaned.append(stripped)
                continue
        if not in_code_block and stripped.startswith('--') and not any(kw in stripped.lower() for kw in ['param', 'return', 'function', 'local']):
            continue
        cleaned.append(line)
    
    code = '\n'.join(cleaned).strip()
    
    if code.startswith('-- local function') or code.startswith('-- function'):
        code = re.sub(r'^--\s*', '', code, flags=re.MULTILINE)
    
    end_match = re.search(r'\bend\b\s*$', code, re.MULTILINE)
    if end_match:
        code = code[:end_match.end()].strip()
    
    return code if code else ""


def template_validation(code: str) -> Tuple[bool, Optional[str]]:
    if not code:
        return True, None
    errors = []
    if re.search(r'function\s+\w+\s*\([^)]*\)\s*end', code, re.DOTALL):
        if 'return' not in code and 'print' not in code and 'error' not in code:
            errors.append("Функция не возвращает значение")
    if code.count('"') % 2 != 0 or code.count("'") % 2 != 0:
        errors.append("Возможно, незакрытая строка")
    if code.count('(') != code.count(')'):
        errors.append("Несовпадение скобок ()")
    if code.count('{') != code.count('}'):
        errors.append("Несовпадение скобок {}")
    if code.count('if') > code.count('end') or code.count('while') > code.count('end'):
        errors.append("Незавершённый блок if/while")
    return len(errors) == 0, "; ".join(errors) if errors else None


async def validate_lua_code(code: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
    if not code or code.strip().startswith("⚠️"):
        return True, None
    try:
        process = await asyncio.create_subprocess_exec(
            "luac", "-p", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(code.encode('utf-8')),
            timeout=timeout
        )
        if process.returncode != 0:
            return False, stderr.decode('utf-8', errors='replace').strip()
    except FileNotFoundError:
        logger.warning("luac не найден, пропускаю проверку")
    except asyncio.TimeoutError:
        return False, "Таймаут валидации"
    except Exception as e:
        return False, str(e)
    
    is_template_ok, template_error = template_validation(code)
    if not is_template_ok:
        return False, f"Шаблон: {template_error}"
    return True, None


async def clarification_node(state: AgentState) -> AgentState:
    query = state["messages"][-1].content if state["messages"] else ""
    unclear_patterns = [r'^сделай$', r'^напиши код$', r'^помоги$', r'^test$', r'^как [а-я]+$', r'^function$', r'^lua$']
    words = query.split()
    is_unclear = len(words) < 3 or any(re.search(p, query.lower()) for p in unclear_patterns) or (len(query) < 20 and '?' not in query and 'function' not in query.lower())
    
    if is_unclear:
        clarification = "Уточните: какую функцию создать? Какие параметры и возврат?"
        logger.info(f"Запрос неясен: '{query[:40]}...'")
        return {"messages": [AIMessage(content=clarification)], "current_code": "", "needs_clarification": True}
    return {"needs_clarification": False}


async def retrieval_node(state: AgentState) -> AgentState:
    if state.get("skip_rag", False) or state.get("needs_clarification", False):
        return {"rag_chunks": []}
    query = state["messages"][-1].content if state["messages"] else ""
    needs_rag = any(kw in query.lower() for kw in ["документация", "синтаксис", "как работает", "что такое", "параметры", "возвращает", "пример из", "описание", "библиотека"])
    if needs_rag:
        try:
            chunks: List[RAGChunk] = await rag_service.search(query=query, user_id=state["user_id"], top_k=3)
            logger.info(f"RAG: {len(chunks)} чанков")
            return {"rag_chunks": chunks}
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return {"rag_chunks": []}
    return {"rag_chunks": []}


async def generation_node(state: AgentState) -> AgentState:
    try:
        messages = state["messages"]
        user_query = messages[-1].content if messages else ""
        rag_chunks = state.get("rag_chunks") or []
        
        fast_mode = state.get("fast_mode", False) or state.get("skip_rag", False)
        if fast_mode:
            temperature = 0.1
            num_ctx = 1024
            num_predict = 128
        else:
            temperature = 0.2
            num_ctx = 2048
            num_predict = 256
        
        chat_history = [
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
            for m in messages[:-1] if isinstance(m, (HumanMessage, AIMessage))
        ]
        
        prompt = build_rag_prompt(query=user_query, context_chunks=rag_chunks, chat_history=chat_history)
        
        full_response = ""
        async for token in stream_chat(
            prompt=prompt,
            system_prompt="",
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict
        ):
            full_response += token
        
        code = extract_code_block(full_response)
        logger.info(f"Генерация: код={bool(code)}, fast={fast_mode}")
        
        return {
            "messages": [AIMessage(content=full_response)],
            "current_code": code or full_response,
            "attempts": state.get("attempts", 0) + 1,
            "validation_error": None
        }
    except Exception as e:
        logger.error(f"Gen error: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"⚠️ Ошибка: {str(e)}")],
            "current_code": "",
            "validation_error": str(e),
            "attempts": state.get("attempts", 0) + 1
        }


async def validation_node(state: AgentState) -> AgentState:
    code = state.get("current_code", "")
    if not code or code.strip().startswith("⚠️"):
        return {"validation_error": None}
    is_valid, error = await validate_lua_code(code)
    if is_valid:
        logger.info("✓ Код валиден")
        return {"validation_error": None}
    logger.warning(f"✗ Ошибка: {error}")
    return {"validation_error": error}


async def execution_node(state: AgentState) -> AgentState:
    if not state.get("run_tests", False):
        return {"execution_result": None}
    code = state.get("current_code", "")
    if not code or code.strip().startswith("⚠️"):
        return {"execution_result": None}
    try:
        result = await sandbox_service.execute(code, timeout=5)
        logger.info(f"Sandbox: success={result.success}")
        if not result.success:
            return {"execution_result": result, "validation_error": f"Runtime: {result.error}"}
        return {"execution_result": result}
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return {"execution_result": SandboxResult(success=False, error=str(e))}


def router(state: AgentState) -> Literal["clarify", "generate", "execute", "end"]:
    attempts = state.get("attempts", 0)
    has_error = bool(state.get("validation_error"))
    needs_clarification = state.get("needs_clarification", False)
    
    if needs_clarification:
        logger.info("Возвращаю вопрос на уточнение")
        return "end"
    if has_error and attempts < 1:
        logger.info(f"Попытка {attempts + 1}/1")
        return "generate"
    if state.get("run_tests", False):
        return "execute"
    return "end"


def create_lua_agent():
    workflow = StateGraph(AgentState)
    workflow.add_node("clarify", clarification_node)
    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("generate", generation_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("execute", execution_node)
    
    workflow.set_entry_point("clarify")
    workflow.add_edge("clarify", "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "validate")
    
    workflow.add_conditional_edges(
        "validate", router,
        {"clarify": "clarify", "generate": "generate", "execute": "execute", "end": END}
    )
    workflow.add_edge("execute", END)
    
    return workflow.compile()


lua_agent = create_lua_agent()