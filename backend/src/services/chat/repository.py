from sqlalchemy.ext.asyncio import AsyncSession
from src.services.chat.base import ChatRepository
from src.models.chat import Chat
from typing import Optional, List
from sqlalchemy import select, desc
from datetime import datetime, timezone


class SQLAlchemyChatRepository(ChatRepository):
    def __init__(self, session: AsyncSession):
        self.session = session 

    async def get_by_id(self, chat_id: str) -> Optional[Chat]:
        query = select(Chat).where(Chat.id==chat_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_id_for_user(self, chat_id: str, user_id: str) -> Optional[Chat]:
        query = select(Chat).where(Chat.id==chat_id, Chat.user_id==user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_chats(self, user_id: str, limit: int = 20) -> List[Chat]:
        query = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(desc(Chat.updated_at))
            .limit(limit) 
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, data: dict) -> Chat:
        chat = Chat(**data)
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat 
    
    async def update(self, chat_id: str, data: dict) -> Optional[Chat]: 
        chat = await self.get_by_id(chat_id)
        if not chat:
            return None
        
        for field, value in data.items():
            if hasattr(chat, field):
                setattr(chat, field, value)
        
        chat.updated_at = datetime.now(timezone.utc) 
        await self.session.commit()
        await self.session.refresh(chat)
        return chat
    
    async def delete(self, chat_id: str) -> bool:
        chat = await self.get_by_id(chat_id)
        if not chat:
            return False 
        
        await self.session.delete(chat)
        await self.session.commit()
        return True