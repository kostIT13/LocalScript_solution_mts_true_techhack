import uuid
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.user.repository import SQLAlchemyUserRepository
from src.models.user import User
from typing import Optional, List


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SQLAlchemyUserRepository(db)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        return await self.repository.get_by_id(user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        users = await self.repository.get_all(email=email)
        return users[0] if users else None
    
    async def get_all_users(self, **filters) -> List[User]:
        return await self.repository.get_all(**filters)

    async def create_user(self, data: dict) -> User: 
        password = data['password']
        if len(password.encode('utf-8')) > 72:
            raise ValueError("Пароль слишком длинный (макс. 72 байта)")
        if len(password) < 6:
            raise ValueError("Пароль слишком короткий (мин. 6 символов)")
        
        existing_users = await self.repository.get_all(email=data['email'])
        if existing_users:
            raise ValueError("Email уже занят")
        
        existing = await self.repository.get_all(username=data.get('username'))
        if existing:
            
            raise ValueError("Username уже занят")
        hashed_password = self._hash_password(password)
        
        user = await self.repository.create({
            "id": str(uuid.uuid4()),
            "email": data['email'],
            "username": data['username'],
            "hashed_password": hashed_password,
            "is_active": True,
            "is_superuser": False
        })
        return user

    async def update_user(self, user_id: str, data: dict) -> Optional[User]:
        if 'password' in data:
            new_password = data['password']
            if len(new_password.encode('utf-8')) > 72:
                raise ValueError("Пароль слишком длинный (макс. 72 байта)")
            
            data['hashed_password'] = self._hash_password(new_password)
            del data['password']
        
        return await self.repository.update(user_id, data)
    
    async def delete_user(self, user_id: str) -> bool:
        return await self.repository.delete(user_id)

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def _verify_password(password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except (ValueError, TypeError):
            return False