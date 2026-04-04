from abc import ABC, abstractmethod
from typing import Optional, List
from src.models.generation import CodeGeneration


class GenerationRepository(ABC):
    @abstractmethod
    async def get_generation(self, genertion_id: str) -> Optional[CodeGeneration]:
        raise NotImplementedError
    
    @abstractmethod
    async def get_user_history(self, user_id: str, limit: int = 20) -> List[CodeGeneration]:
        raise NotImplementedError
    
    @abstractmethod
    async def create(self, data: dict) -> CodeGeneration:
        raise NotImplementedError
    
    @abstractmethod 
    async def update(self, generation_id: str, data: dict) -> Optional[CodeGeneration]:
        raise NotImplementedError
    
    @abstractmethod
    async def delete(self, generation_id: str) -> bool:
        raise NotImplementedError
                                                   