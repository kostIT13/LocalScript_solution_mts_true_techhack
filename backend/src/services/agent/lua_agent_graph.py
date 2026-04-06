import re
import asyncio
from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.services.llm.generator import stream_chat
from src.services.llm.promts import LUA_AGENT_SYSTEM_PROMPT

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  
    current_code: str                        
    validation_error: Optional[str]          
    attempts: int                            
    rag_context: Optional[str]              

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
        return True, None
    except Exception as e:
        return False, str(e)

async def generation_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    
    context = [{"role": "system", "content": LUA_AGENT_SYSTEM_PROMPT}]
    
    if state.get("rag_context"):
        context.append({
            "role": "system",
            "content": f"СПРАВОЧНАЯ ИНФОРМАЦИЯ (используй это):\n{state['rag_context']}"
        })
    
    context += [{"role": m.type if hasattr(m, 'type') else m.role, "content": m.content} for m in messages]
    
    if state.get("validation_error"):
        last_msg = context.pop()  
        context.append({
            "role": "user",
            "content": f"{last_msg['content']}\n\nОШИБКА: {state['validation_error']}\n\nИсправь код и верни ТОЛЬКО исправленный блок ```lua ... ```."
        })
    
    full_response = ""
    async for token in stream_chat(
        prompt=context[-1]["content"],  
        system_prompt="\n".join(c["content"] for c in context[:-1]),
        temperature=0.2,
        num_ctx=4096
    ):
        full_response += token
    
    code = extract_code_block(full_response)
    
    return {
        "messages": [AIMessage(content=full_response)],
        "current_code": code or full_response,
        "attempts": state.get("attempts", 0) + 1
    }

async def validation_node(state: AgentState) -> AgentState:
    code = state.get("current_code", "")
    if not code:
        return {"validation_error": "Пустой код"}
    
    is_valid, error = await validate_lua_code(code)
    return {"validation_error": None if is_valid else error}

def router(state: AgentState) -> Literal["generate", "end"]:
    if state.get("validation_error") and state.get("attempts", 0) < 3:
        return "generate"  
    return "end"  

def create_lua_agent():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("generate", generation_node)
    workflow.add_node("validate", validation_node)
    
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "validate")
    workflow.add_conditional_edges(
        "validate",
        router,
        {"generate": "generate", "end": END}
    )
    
    return workflow.compile()

lua_agent = create_lua_agent()