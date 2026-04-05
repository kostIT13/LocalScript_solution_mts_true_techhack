from abc import ABC, abstractmethod
from typing import Optional, List
from src.models.user import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def get_all(self, **filters) -> List[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def create(self, data: dict) -> User:
        raise NotImplementedError
    
    @abstractmethod 
    async def update(self, user_id: str, data: dict) -> Optional[User]:
        raise NotImplementedError
    
    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        raise NotImplementedError