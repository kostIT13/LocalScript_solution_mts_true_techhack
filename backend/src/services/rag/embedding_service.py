import logging
from typing import List
from src.services.rag.ollama_client import ollama_client

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = ollama_client
        logger.info("EmbeddingService инициализирован")
    
    def embed_text(self, text: str) -> List[float]:
        if not text.strip():
            return []
        return self.client.embed_text(text)
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        valid_texts = [t for t in texts if t.strip()]
        if not valid_texts:
            return []
        return self.client.embed_texts(valid_texts)
    
    def normalize_embeddings(self, embeddings: List[List[float]]) -> List[List[float]]:
        import math
        normalized = []
        for emb in embeddings:
            norm = math.sqrt(sum(x * x for x in emb))
            if norm > 0:
                normalized.append([x / norm for x in emb])
            else:
                normalized.append(emb)
        return normalized


embedding_service = EmbeddingService()