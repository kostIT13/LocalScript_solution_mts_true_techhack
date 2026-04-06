import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from src.services.chat.base import ChatRepository
from src.models.chat import Chat, Message
from src.services.chat.repository import SQLAlchemyChatRepository


logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SQLAlchemyChatRepository(db)

    async def create_chat(self, user_id: str, title: str = "Новый чат") -> Chat:
        title = (title or "Новый чат").strip()[:200]
        return await self.repository.create({"user_id": user_id, "title": title})

    async def get_chat(self, chat_id: str, user_id: str) -> Chat:
        chat = await self.repository.get_by_id_for_user(chat_id, user_id)
        if not chat:
            raise ValueError("Чат не найден или доступ запрещен")
        return chat

    async def list_chats(self, user_id: str, limit: int = 20) -> List[Chat]:
        limit = max(1, min(limit, 100))
        return await self.repository.get_user_chats(user_id, limit)

    async def update_title(self, chat_id: str, user_id: str, title: str) -> Chat:
        await self.get_chat(chat_id, user_id)
        if not title.strip():
            raise ValueError("Заголовок не может быть пустым")
        return await self.repository.update(chat_id, {"title": title.strip()[:200]})

    async def delete_chat(self, chat_id: str, user_id: str) -> bool:
        await self.get_chat(chat_id, user_id) 
        return await self.repository.delete(chat_id)

    async def add_message(
        self,
        chat_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Message:
        await self.get_chat(chat_id, user_id)
        
        if len(content) > 8000:
            raise ValueError("Сообщение слишком длинное (макс. 8000 символов)")
        
        msg = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            metadata_=metadata or {}
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def get_messages(self, chat_id: str, user_id: str, limit: int = 50) -> List[Message]:
        await self.get_chat(chat_id, user_id)
        limit = max(1, min(limit, 100))
        
        query = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def process_user_message(self, chat_id: str, user_id: str, content: str) -> Message:
        user_msg = await self.add_message(chat_id, user_id, "user", content)

        assistant_msg = await self.add_message(
            chat_id=chat_id,
            user_id=user_id,
            role="assistant",
            content=f"🤖 Заглушка: получил '{content[:30]}...'",
            metadata_={"status": "mock", "model": "placeholder"}
        )
        
        logger.info(f"Обработано сообщение в чате {chat_id} от {user_id}")
        return assistant_msg