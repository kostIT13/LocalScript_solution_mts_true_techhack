from sqlalchemy.ext.asyncio import AsyncSession
from src.services.generation.base import GenerationRepository
from typing import Optional, List 
from src.models.generation import CodeGeneration
from sqlalchemy import select
from datetime import datetime, timezone


class SQLAlchemyGenerationRepository(GenerationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session 

    async def get_generation(self, generation_id: str) -> Optional[CodeGeneration]:
        result = await self.session.get(CodeGeneration, generation_id)
        return result 
    
    async def get_user_history(self, user_id: str) -> List[CodeGeneration]:
        query = select(CodeGeneration).where(CodeGeneration.user_id==user_id).order_by(CodeGeneration.updated_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, data: dict) -> CodeGeneration:
        code_generation = CodeGeneration(**data)
        self.session.add(code_generation)
        await self.session.commit()
        await self.session.refresh(code_generation)
        return code_generation
    
    async def update(self, generation_id: str, data: dict) -> Optional[CodeGeneration]:
        code_generation = await self.get_generation(generation_id)
        if not code_generation:
            return None 
        
        for field, value in data.items():
            if hasattr(code_generation, field):
                setattr(code_generation, field, value)
        
        code_generation.updated_at = datetime.now(timezone.utc) 
        await self.session.commit()
        await self.session.refresh(code_generation)
        return code_generation
    
    async def delete(self, generation_id: str) -> bool:
        code_generation = await self.get_generation(generation_id)
        if not code_generation:
            return None 
        
        await self.session.delete(code_generation)
        await self.session.commit()
        return True