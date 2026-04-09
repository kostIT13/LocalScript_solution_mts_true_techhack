import logging
import hashlib
import uuid
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.models.document import Document, DocumentStatus
from src.services.document.base import DocumentRepository
from src.services.document.repository import SQLAlchemyDocumentRepository
from src.services.rag.rag_service import rag_service
from src.core.database import engine as async_engine
from src.core.config import settings


logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: AsyncSession, upload_dir: str = "uploads"):
        self.db = db
        self.repository = SQLAlchemyDocumentRepository(db)
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentService инициализирован (upload_dir={self.upload_dir})")

    async def get_document_by_id(self, document_id: str, user_id: str) -> Optional[Document]:
        doc = await self.repository.get_by_id(document_id)
        if not doc or doc.user_id != user_id or doc.is_deleted:
            return None
        return doc

    async def get_list_documents(self, user_id: str, limit: int = 20) -> List[Document]:
        limit = max(1, min(limit, 100))
        return await self.repository.get_user_documents(user_id)

    async def upload_document(
        self,
        user_id: str,
        filename: str,
        file_content: bytes,
        file_type: str,
        background_tasks: BackgroundTasks
    ) -> Document:
        allowed_types = [
            "application/pdf",
            "text/plain",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]
        if file_type not in allowed_types:
            raise ValueError(f"Неподдерживаемый тип файла: {file_type}")
        
        if not file_content:
            raise ValueError("Пустой файл не может быть загружен")

        content_hash = hashlib.sha256(file_content).hexdigest()
        
        existing = await self.repository.get_by_content_hash(user_id, content_hash)
        if existing and not existing.is_deleted:
            logger.info(f"Найден дубликат документа: {existing.filename} (id={existing.id})")
            return existing

        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix or ".bin"
        file_path = self.upload_dir / f"{file_id}{ext}"
        
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
            logger.info(f"Файл сохранён: {file_path} ({len(file_content)} байт)")
        except IOError as e:
            logger.error(f"Ошибка записи файла {file_path}: {e}")
            raise ValueError(f"Не удалось сохранить файл: {e}")

        now = datetime.now(timezone.utc)
        
        doc = await self.repository.create({
            "id": file_id,
            "user_id": user_id,
            "filename": filename,
            "file_path": str(file_path),
            "file_size": len(file_content),
            "file_type": file_type,
            "content_hash": content_hash,
            "status": DocumentStatus.PENDING,
            "chunk_count": 0,
            "collection_name": "lua_docs", 
            "metadata_": {"original_filename": filename},
            "created_at": now,
            "updated_at": now
        })
        
        logger.info(f"Документ создан в БД: {doc.id} ({doc.filename})")
        
        background_tasks.add_task(self._index_document_safe, doc.id)
        
        return doc

    async def delete_document(self, document_id: str, user_id: str, hard: bool = False) -> bool:
        doc = await self.get_document_by_id(document_id, user_id)
        if not doc:
            logger.warning(f"Документ {document_id} не найден или доступ запрещён")
            return False
        
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
                logger.info(f"Файл удалён с диска: {doc.file_path}")
            except OSError as e:
                logger.error(f"Ошибка удаления файла {doc.file_path}: {e}")
        
        try:
            await rag_service.delete_from_index(document_id, user_id)
            logger.info(f"Документ {document_id} удалён из векторного индекса")
        except ImportError:
            logger.warning("RAG-сервис недоступен, пропуск удаления из индекса")
        except Exception as e:
            logger.error(f"Ошибка удаления из индекса: {e}")
        
        if hard:
            result = await self.repository.hard_delete(document_id)
            if result:
                logger.info(f"Документ {document_id} полностью удалён из БД (hard delete)")
        else:
            result = await self.repository.delete(document_id) 
            if result:
                logger.info(f"Документ {document_id} помечен как удалённый (soft delete)")
        
        return result

    async def retry_indexing(self, document_id: str, user_id: str) -> bool:
        doc = await self.get_document(document_id, user_id)
        if not doc:
            return False
        
        if doc.status == DocumentStatus.COMPLETED:
            logger.warning(f"Документ {document_id} уже проиндексирован")
            return True
        
        doc.status = DocumentStatus.PENDING
        doc.error_message = None
        await self.db.commit()
        
        from fastapi import BackgroundTasks
        await self._index_document_safe(document_id)
        return True

    async def _index_document_safe(self, document_id: str):
        async with AsyncSession(async_engine) as session:
            try:
                logger.info(f"[INDEX] Начинаю индексацию (id={document_id})")
                
                doc = await self.repository.get_by_id(document_id)
                if not doc:
                    logger.error(f"Документ {document_id} не найден в БД")
                    return
                
                doc.status = DocumentStatus.PROCESSING
                doc.updated_at = datetime.now(timezone.utc)
                await session.commit()
            
                result = await rag_service.index_document(doc, db_session=session)
                
                if result.success:
                    doc.status = DocumentStatus.COMPLETED
                    doc.chunk_count = result.chunk_count
                    doc.processed_at = datetime.now(timezone.utc)
                    doc.error_message = None
                    logger.info(f"[INDEX] Документ {document_id} проиндексирован ({result.chunk_count} чанков)")
                else:
                    doc.status = DocumentStatus.FAILED
                    doc.error_message = result.error
                    logger.error(f"[INDEX] Индексация {document_id} не удалась: {result.error}")
                
                await session.commit()
                    
            except ImportError as e:
                logger.warning(f"[INDEX] RAG-сервис недоступен: {e}")
            except Exception as e:
                logger.error(f"[INDEX] Критическая ошибка индексации {document_id}: {type(e).__name__}: {e}", exc_info=True)
                try:
                    await session.rollback()
                    doc = await self.repository.get_by_id(document_id)
                    if doc:
                        doc.status = DocumentStatus.FAILED
                        doc.error_message = f"{type(e).__name__}: {str(e)}"
                        await session.commit()
                except Exception as rollback_error:
                    logger.error(f"[INDEX] Не удалось обновить статус после ошибки: {rollback_error}")

    async def _get_file_content(self, file_path: str) -> bytes:
        with open(file_path, "rb") as f:
            return f.read()