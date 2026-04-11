import os
import logging
from typing import AsyncGenerator, Optional
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from src.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _get_chat_llm(
    model: str,
    temperature: float,
    base_url: str,
    num_ctx: int,
    num_predict: int,
    num_batch: int,
    num_parallel: int
):
    logger.debug(f"LLM init: {model}, ctx={num_ctx}, predict={num_predict}")
    
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        model_kwargs={
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_batch": num_batch,
            "num_parallel": num_parallel,
            "repeat_penalty": 1.1,
        },
    )


async def stream_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    num_ctx: Optional[int] = None,
    num_predict: Optional[int] = None,
    num_batch: Optional[int] = None,
    num_parallel: Optional[int] = None,
    model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    final_ctx = num_ctx or int(os.getenv("NUM_CTX", 1024))
    final_predict = num_predict or int(os.getenv("NUM_PREDICT", 200))
    final_batch = num_batch or int(os.getenv("NUM_BATCH", 1))
    final_parallel = num_parallel or int(os.getenv("NUM_PARALLEL", 1))
    
    llm = _get_chat_llm(
        model=model or settings.OLLAMA_LLM_MODEL,
        temperature=temperature,
        base_url=settings.OLLAMA_HOST.rstrip("/"),
        num_ctx=final_ctx,
        num_predict=final_predict,
        num_batch=final_batch,
        num_parallel=final_parallel
    )
    
    chain = llm | StrOutputParser()
    
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    
    async for token in chain.astream(messages):
        yield token