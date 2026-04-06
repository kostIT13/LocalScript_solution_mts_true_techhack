from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class ChatCreate(BaseModel):
    title: str = Field(default="Новый чат", min_length=1, max_length=255)


class ChatUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ChatMessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    context_length: int = Field(default=4096, ge=512, le=8192)  


class ChatMessageResponse(BaseModel):
    id: str 
    role: str 
    content: str
    sources: List[str] = Field(default_factory=list)
    chat_id: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChatListResponse(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None  
    
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: List[str] = Field(default_factory=list)  
    created_at: datetime
    is_starred: bool
    
    model_config = ConfigDict(from_attributes=True)


class ChatBaseResponse(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
    

class ChatResponse(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[MessageResponse] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)