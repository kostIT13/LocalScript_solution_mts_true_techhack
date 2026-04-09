from typing import AsyncGenerator, List, Dict, Optional
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from src.core.config import settings


@lru_cache(maxsize=2)
def _get_chat_llm(model: str, temperature: float, base_url: str, num_ctx: int):
    """Кэшированный экземпляр ChatOllama."""
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        model_kwargs={"num_ctx": num_ctx} if num_ctx else None,
    )


async def stream_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    num_ctx: int = 4096,
    model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    llm = _get_chat_llm(
        model=model or settings.OLLAMA_LLM_MODEL,
        temperature=temperature,
        base_url=settings.OLLAMA_HOST.rstrip("/"),
        num_ctx=num_ctx
    )
    
    chain = llm | StrOutputParser()
    
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    
    async for token in chain.astream(messages):
        yield token