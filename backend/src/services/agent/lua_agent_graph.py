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


def extract_code_block(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"```(?:lua)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
        return _clean_lua_code(code) if code else None
    if re.match(r"^\s*(local|function|return|if|while|for)", text, re.MULTILINE):
        return _clean_lua_code(text.strip())
    return None


def _clean_lua_code(code: str) -> str:
    code = re.sub(r'\[Источник:[^\]]*\]\s*', '', code)
    code = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', code)
    
    garbage_patterns = [
        r'ДОКУМЕНТАЦИЯ:.*$',
        r'КОНТЕКСТ:.*$',
        r'Пользователь:.*$',
        r'Ассистент:.*$',
        r'ЗАПРОС:.*$',
        r'Твой ответ:.*$',
        r'^-- \[Источник:[^\]]*\].*$',
    ]
    for pattern in garbage_patterns:
        code = re.sub(pattern, '', code, flags=re.MULTILINE | re.IGNORECASE)
    
    lines = code.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not cleaned and stripped.startswith('--') and 'function' not in stripped.lower():
            continue
        cleaned.append(line)
    
    code = '\n'.join(cleaned).strip()
    
    if code.startswith('-- local function') or code.startswith('-- function'):
        code = re.sub(r'^--\s*', '', code, flags=re.MULTILINE)
    
    return code


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
        if process.returncode == 0:
            return True, None
        return False, stderr.decode('utf-8').strip()
    except FileNotFoundError:
        return True, None
    except asyncio.TimeoutError:
        return False, "Превышено время валидации"
    except Exception as e:
        return False, str(e)


async def retrieval_node(state: AgentState) -> AgentState:
    if state.get("skip_rag", False):
        return {"rag_chunks": []}
    
    query = state["messages"][-1].content if state["messages"] else ""
    try:
        chunks = await rag_service.search(query=query, user_id=state["user_id"], top_k=3)
        return {"rag_chunks": chunks}
    except Exception as e:
        logger.error(f"RAG error: {e}")
        return {"rag_chunks": []}


async def generation_node(state: AgentState) -> AgentState:
    try:
        messages = state["messages"]
        user_query = messages[-1].content if messages else ""
        rag_chunks = state.get("rag_chunks") or []
        prompt = build_rag_prompt(
            query=user_query,
            context_chunks=rag_chunks,
            chat_history=[] 
        )
        
        full_response = ""
        async for token in stream_chat(
            prompt=prompt,
            system_prompt="",
            temperature=0.1,  
            num_ctx=2048    
        ):
            full_response += token
        
        code = extract_code_block(full_response)
        logger.info(f"Генерация: код={bool(code)}")
        
        return {
            "messages": [AIMessage(content=full_response)],
            "current_code": code or full_response,
            "attempts": state.get("attempts", 0) + 1,
            "validation_error": None
        }
    except Exception as e:
        logger.error(f"Gen error: {e}")
        return {
            "messages": [AIMessage(content=str(e))],
            "current_code": "",
            "validation_error": str(e),
            "attempts": state.get("attempts", 0) + 1
        }


async def validation_node(state: AgentState) -> AgentState:
    code = state.get("current_code", "")
    if not code:
        return {"validation_error": None}
    
    is_valid, error = await validate_lua_code(code)
    if is_valid:
        return {"validation_error": None}
    return {"validation_error": error}


async def execution_node(state: AgentState) -> AgentState:
    if not state.get("run_tests", False):
        return {"execution_result": None}
    
    code = state.get("current_code", "")
    if not code:
        return {"execution_result": None}
    
    try:
        result = await sandbox_service.execute(code, timeout=5)
        return {"execution_result": result}
    except Exception as e:
        return {"execution_result": SandboxResult(success=False, error=str(e))}


def router(state: AgentState) -> Literal["generate", "execute", "end"]:
    attempts = state.get("attempts", 0)
    has_error = bool(state.get("validation_error"))
    
    if has_error and attempts < 1:
        return "generate"
    
    if state.get("run_tests", False):
        return "execute"
        
    return "end"


def create_lua_agent():
    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("generate", generation_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("execute", execution_node)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "validate")
    
    workflow.add_conditional_edges(
        "validate", router,
        {"generate": "generate", "execute": "execute", "end": END}
    )
    workflow.add_edge("execute", END)
    
    return workflow.compile()


lua_agent = create_lua_agent()