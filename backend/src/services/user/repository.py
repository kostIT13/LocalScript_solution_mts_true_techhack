from src.services.user.base import UserRepository
from src.models.user import User 
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session 


    async def get_by_id(self, user_id: str) -> Optional[User]:
        query = select(User).where(User.id==user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() 

    async def get_all(self, **filters) -> List[User]:
        query = select(User)
        for field, value in filters.items():
            if hasattr(User, field):
                query = query.where(getattr(User, field) == value)
        result = await self.session.execute(query)
        return list(result.scalars().all())


    async def create(self, data: dict) -> User:
        user = User(**data)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    

    async def update(self, user_id: str, data: dict) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None 
        
        for field, value in data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user 
    

    async def delete(self, user_id: str) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False 
        await self.session.delete(user)
        await self.session.commit()
        return True
