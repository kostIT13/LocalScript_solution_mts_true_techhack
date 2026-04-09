import logging
from typing import Optional, List, AsyncGenerator
from src.core.config import settings
import asyncio
import ollama

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.embedding_model = settings.OLLAMA_EMBEDDING_MODEL
        self.llm_model = settings.OLLAMA_LLM_MODEL
        self.base_url = settings.OLLAMA_HOST.rstrip("/")
        self._client = None
        logger.info(f"OllamaClient инициализирован (хост={self.base_url})")
    
    @property
    def client(self):
        if self._client is None:
            try:
                headers = {}
                self._client = ollama.Client(
                    host=self.base_url,
                    headers=headers if headers else None
                )
                models = self._client.list()
                model_names = [m.get("name") for m in models.get("models", [])]
                logger.info(f"Ollama подключён. Доступные модели: {model_names}")
            except Exception as e:
                logger.error(f"Ошибка подключения к Ollama: {e}")
                raise
        return self._client
    
    def embed_text(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Ошибка эмбеддинга для '{text[:50]}...': {e}")
            raise
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]
    
    def generate(
        self, 
        prompt: str, 
        system: str = "", 
        temperature: float = 0.2,
        num_ctx: int = 4096
    ) -> str:
        try:
            response = self.client.generate(
                model=self.llm_model,
                prompt=prompt,
                system=system,
                options={
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": 2048,
                    "num_ctx": num_ctx
                }
            )
            return response.get("response", "")
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            raise
    
    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        num_ctx: int = 4096
    ) -> AsyncGenerator[str, None]:
        try:
            def _sync_stream():
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                stream = self.client.chat(
                    model=self.llm_model,
                    messages=messages,
                    stream=True,
                    options={
                        "temperature": temperature,
                        "top_p": 0.9,
                        "num_ctx": num_ctx
                    }
                )
                
                for chunk in stream:
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
            
            loop = asyncio.get_event_loop()
            tokens = await loop.run_in_executor(None, lambda: list(_sync_stream()))
            for token in tokens:
                yield token
                await asyncio.sleep(0.001)
                    
        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"\n[Ошибка: {str(e)}]"


ollama_client = OllamaClient()