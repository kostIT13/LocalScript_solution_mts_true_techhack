from src.services.document.base import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from src.models.document import Document, DocumentStatus
from sqlalchemy import select
from datetime import datetime, timezone


class SQLAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session 

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        result = await self.session.get(Document, document_id)
        return result
    
    async def get_user_documents(self, user_id: str) -> List[Document]:
        query = select(Document).where(
            Document.user_id == user_id,
            Document.is_deleted == False
        ).order_by(Document.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, data: dict) -> Document:
        document = Document(**data)
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document
    
    async def update(self, document_id: str, data: dict) -> Optional[Document]:
        doc = await self.get_by_id(document_id)
        if not doc:
            return None
        
        for field, value in data.items():
            if hasattr(doc, field):
                setattr(doc, field, value)
        
        await self.session.commit()
        await self.session.refresh(doc)
        return doc
    
    async def delete(self, document_id: str) -> bool:
        doc = await self.get_by_id(document_id)
        if not doc:
            return False
        
        doc.is_deleted = True
        doc.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return True
    
    async def hard_delete(self, document_id: str) -> bool:
        doc = await self.get_by_id(document_id)
        if not doc:
            return False
        
        await self.session.delete(doc)
        await self.session.commit()
        return True

    async def get_by_status(self, user_id: str, status: DocumentStatus) -> List[Document]:
        query = select(Document).where(
            Document.user_id == user_id,
            Document.status == status,
            Document.is_deleted == False
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_by_content_hash(self, user_id: str, content_hash: str) -> Optional[Document]:
        query = select(Document).where(
            Document.user_id == user_id,
            Document.content_hash == content_hash,
            Document.is_deleted == False
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()