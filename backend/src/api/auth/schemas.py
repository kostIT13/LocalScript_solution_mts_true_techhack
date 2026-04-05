# backend/src/api/auth/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr 
    username: str = Field(..., min_length=3, max_length=50) 
    password: str = Field(..., min_length=6) 

    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Пароль слишком длинный (макс. 72 байта для bcrypt)')
        return v

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)