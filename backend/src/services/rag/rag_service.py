import logging
import asyncio
from typing import List, Optional, AsyncGenerator
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.document import Document, DocumentStatus
from src.services.rag.chroma_client import chroma_client
from src.services.rag.embedding_service import embedding_service
from src.services.rag.document_processor import document_processor
from src.services.rag.ollama_client import ollama_client
from src.services.prompts.lua_rag_agent_prompt import build_rag_prompt
from src.services.document.repository import SQLAlchemyDocumentRepository
from src.services.rag.rag_chank import RAGChunk


logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    success: bool
    chunk_count: int = 0
    error: Optional[str] = None


class RAGService:
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session
        self.chroma = chroma_client
        self.embeddings = embedding_service
        self.processor = document_processor
        self.llm = ollama_client
        
        logger.info("RAGService инициализирован")
    
    async def _get_repository(self, session: Optional[AsyncSession] = None):
        if not session and not self.db_session:
            return None
        return SQLAlchemyDocumentRepository(session or self.db_session)
    
    async def index_document(self, document: Document, db_session: Optional[AsyncSession] = None) -> IndexResult:
        session = db_session or self.db_session
        
        try:
            logger.info(f"[INDEX] Начинаю: {document.filename} (id={document.id})")
            
            chunks = self.processor.process(document.file_path, document.file_type)
            if not chunks:
                return IndexResult(success=False, error="Пустой документ или ошибка извлечения текста")
            
            logger.info(f"Создано {len(chunks)} чанков")
            
            texts = [chunk.page_content for chunk in chunks]
            embeddings_list = self.embeddings.embed_texts(texts)
            if len(embeddings_list) != len(chunks):
                return IndexResult(success=False, error="Несоответствие чанков и эмбеддингов")
            
            logger.info(f"Создано {len(embeddings_list)} эмбеддингов")
            
            metadatas = [
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "user_id": document.user_id,
                    "chunk_index": chunk.metadata.get("chunk_index", i),
                    "source": chunk.metadata.get("source", document.filename)
                }
                for i, chunk in enumerate(chunks)
            ]
            
            ids = [f"{document.id}_{i}" for i in range(len(chunks))]
            
            self.chroma.add_documents(
                ids=ids,
                embeddings=embeddings_list,
                documents=texts,
                metadatas=metadatas
            )
            
            if session:
                repo = await self._get_repository(session)
                if repo:
                    await repo.update(document.id, {
                        "status": DocumentStatus.COMPLETED,
                        "chunk_count": len(chunks),
                        "processed_at": datetime.now(timezone.utc),
                        "error_message": None
                    })
                    await session.commit()
                    logger.info(f"Статус {document.id} → COMPLETED")
            
            logger.info(f"Индексация завершена: {len(chunks)} чанков")
            return IndexResult(success=True, chunk_count=len(chunks))
            
        except Exception as e:
            logger.error(f"Ошибка индексации {document.id}: {type(e).__name__}: {e}", exc_info=True)
            
            if session:
                try:
                    repo = await self._get_repository(session)
                    if repo:
                        await repo.update(document.id, {
                            "status": DocumentStatus.FAILED,
                            "error_message": f"{type(e).__name__}: {str(e)}"
                        })
                        await session.commit()
                except Exception as update_error:
                    logger.error(f"Не удалось обновить статус на FAILED: {update_error}")
            
            return IndexResult(success=False, error=str(e))
    
    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
        document_id: Optional[str] = None
    ) -> List[RAGChunk]:
        try:
            logger.info(f"Поиск: '{query[:50]}...', user={user_id}, k={top_k}")
            
            query_embedding = self.embeddings.embed_text(query)
            if not query_embedding:
                return []
            
            results = self.chroma.query(
                query_embedding=query_embedding,
                n_results=top_k * 2,  
                user_id=user_id,
                document_id=document_id
            )
            
            if not results.get("documents") or not results["documents"][0]:
                logger.info("Не найдено релевантных чанков")
                return []
            
            seen: dict[str, int] = {}
            deduplicated: List[RAGChunk] = []
            
            docs = results["documents"][0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            
            for i, content in enumerate(docs):
                meta = metas[i] if i < len(metas) else {}
                distance = dists[i] if i < len(dists) else None
                filename = meta.get("filename", "Unknown")
                
                count = seen.get(filename, 0)
                if count >= 3:
                    continue
                
                seen[filename] = count + 1
                score = 1 - distance if distance is not None else 0.0
                
                deduplicated.append(RAGChunk(
                    content=content,
                    filename=filename,
                    source=meta.get("source", ""),
                    chunk_index=meta.get("chunk_index", i),
                    score=round(score, 4),
                    metadata=meta
                ))
                
                if len(deduplicated) >= top_k:
                    break
            
            filenames = list(set(c.filename for c in deduplicated))
            logger.info(f"Найдено {len(deduplicated)} чанков из: {filenames}")
            return deduplicated
            
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}", exc_info=True)
            return []
    
    async def generate_answer(
        self,
        query: str,
        user_id: str,
        chat_history: Optional[List[dict]] = None,
        temperature: float = 0.2
    ) -> dict:
        chunks = await self.search(query, user_id, top_k=10)
        
        if not chunks:
            return {
                "answer": "К сожалению, я не нашёл информации по вашему вопросу в загруженных документах. Попробуйте загрузить документацию или перефразировать вопрос.",
                "sources": [],
                "used_chunks": []
            }
        
        context = "\n\n".join([
            f"[Источник: {c.filename}]\n{c.content}"
            for c in chunks[:5] 
        ])
        
        prompt = build_rag_prompt(
            query=query,
            context_chunks=chunks,
            chat_history=chat_history
        )
        
        try:
            answer = await asyncio.to_thread(
                self.llm.generate,
                prompt=prompt,
                system="", 
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            answer = "Произошла ошибка при генерации ответа. Попробуйте позже."
        
        sources = list(set(c.filename for c in chunks if c.filename))
        
        return {
            "answer": answer,
            "sources": sources,
            "used_chunks": [c.model_dump() for c in chunks[:5]]
        }
    
    async def generate_answer_stream(
        self,
        query: str,
        user_id: str,
        chat_history: Optional[List[dict]] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        """Стримит ответ токен за токеном (для SSE)"""
        chunks = await self.search(query, user_id, top_k=10)
        
        context = "\n\n".join([
            f"[Источник: {c.filename}]\n{c.content}"
            for c in chunks[:5]
        ]) if chunks else "ДОКУМЕНТАЦИЯ: Не найдено релевантных фрагментов."
        
        prompt = build_rag_prompt(
            query=query,
            context_chunks=chunks,
            chat_history=chat_history
        )
        
        try:
            async for token in self.llm.generate_stream(
                prompt=prompt,
                system="",
                temperature=temperature
            ):
                yield token
        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"\n[Ошибка: {str(e)}]"
    
    async def delete_from_index(self, document_id: str, user_id: str) -> bool:
        try:
            deleted = self.chroma.delete_by_filter(
                user_id=user_id,
                document_id=document_id
            )
            logger.info(f"Удалено из Chroma: {len(deleted) if deleted else 0} чанков")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления из индекса: {e}")
            return False


rag_service = RAGService(db_session=None)