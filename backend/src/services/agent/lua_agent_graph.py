import re
import asyncio
import logging
from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.services.llm.generator import stream_chat
from src.services.prompts.lua_rag_agent_prompt import build_rag_prompt, LUA_RAG_AGENT_PROMPT
from src.services.rag.rag_service import RAGChunk, rag_service


logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  
    current_code: str                       
    validation_error: Optional[str]          
    attempts: int                           
    rag_context: Optional[str]             
    user_id: str                            
    chat_id: Optional[str]                


def extract_code_block(text: str) -> Optional[str]:
    match = re.search(r"```lua\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else None


async def validate_lua_code(code: str) -> tuple[bool, Optional[str]]:
    try:
        process = await asyncio.create_subprocess_exec(
            "luac", "-p", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate(code.encode('utf-8'))
        
        if process.returncode == 0:
            return True, None
        else:
            error_msg = stderr.decode('utf-8').strip()
            return False, error_msg
    except FileNotFoundError:
        logger.warning("luac не найден, пропускаю валидацию")
        return True, None 
    except Exception as e:
        logger.error(f"Ошибка валидации: {e}")
        return False, str(e)


async def retrieval_node(state: AgentState) -> AgentState:
    query = state["messages"][-1].content if state["messages"] else ""
    
    if "?" in query or any(kw in query.lower() for kw in ["как", "что", "почему", "документация"]):
        try:
            chunks: List[RAGChunk] = await rag_service.search(
                query=query,
                user_id=state["user_id"],
                top_k=10
            )
            if chunks:
                context_str = "\n\n".join([
                    f"[Источник: {c.filename}]\n{c.content}"
                    for c in chunks[:5]
                ])
                logger.info(f"RAG: найдено {len(chunks)} чанков для запроса '{query[:30]}...'")
                return {"rag_context": context_str}
        except Exception as e:
            logger.error(f"Ошибка RAG-поиска: {e}")
    
    return {"rag_context": None}


async def generation_node(state: AgentState) -> AgentState:
    try:
        messages = state["messages"]
        user_query = messages[-1].content if messages else ""
        
        rag_chunks = []
        prompt = build_rag_prompt(
            query=user_query,
            context_chunks=rag_chunks, 
            chat_history=[{"role": m.type, "content": m.content} for m in messages[:-1]]
        )
        
        if state.get("rag_context"):
            prompt = prompt.replace(
                "ДОКУМЕНТАЦИЯ:",
                f"ДОКУМЕНТАЦИЯ:\n{state['rag_context']}\n\n"
            )
        
        full_response = ""
        async for token in stream_chat(
            prompt=prompt,
            system_prompt="", 
            temperature=0.2,
            num_ctx=4096
        ):
            full_response += token
        
        code = extract_code_block(full_response)
        
        logger.info(f"Генерация завершена, код извлечён: {bool(code)}")
        
        return {
            "messages": [AIMessage(content=full_response)],
            "current_code": code or full_response,
            "attempts": state.get("attempts", 0) + 1
        }
        
    except Exception as e:
        logger.error(f"Ошибка в generation_node: {e}", exc_info=True)
        error_msg = f"Произошла ошибка при генерации: {str(e)}"
        return {
            "messages": [AIMessage(content=error_msg)],
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
        logger.info("Код валиден")
        return {"validation_error": None}
    else:
        logger.warning(f"Ошибка валидации: {error}")
        return {"validation_error": error}


def router(state: AgentState) -> Literal["generate", "end"]:
    attempts = state.get("attempts", 0)
    has_error = bool(state.get("validation_error"))
    
    if has_error and attempts < 3:
        logger.info(f"Попытка {attempts + 1}/3: исправляю ошибку")
        return "generate"
    
    if has_error:
        logger.warning(f"⚠️ Достигнут лимит попыток ({attempts}), возвращаю последний код")
    
    return "end"


def create_lua_agent():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("retrieve", retrieval_node)      
    workflow.add_node("generate", generation_node)   
    workflow.add_node("validate", validation_node)    
    
    workflow.set_entry_point("retrieve")
    
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "validate")
    
    workflow.add_conditional_edges(
        "validate",
        router,
        {
            "generate": "generate",
            "end": END
        }
    )
    
    return workflow.compile()


lua_agent = create_lua_agent()