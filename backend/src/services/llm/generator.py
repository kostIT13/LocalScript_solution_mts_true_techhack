from typing import AsyncGenerator, List, Dict, Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from src.core.config import settings


def _to_langchain_messages(messages: List[Dict[str, str]]) -> List:
    lc_msgs = []
    for msg in messages:
        role = msg.get("role", "").lower()
        content = msg.get("content", "")
        if role == "system":
            lc_msgs.append(SystemMessage(content=content))
        elif role == "user":
            lc_msgs.append(HumanMessage(content=content))
        else:
            lc_msgs.append(AIMessage(content=content))
    return lc_msgs

async def stream_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    num_ctx: int = 4096,
    model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    llm = ChatOllama(
        model=model or settings.OLLAMA_LLM_MODEL,
        temperature=temperature,
        num_ctx=num_ctx,
        base_url=settings.OLLAMA_HOST.rstrip("/"),
    )
    
    chain = llm | StrOutputParser()
    
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    
    async for token in chain.astream(messages):
        yield token  