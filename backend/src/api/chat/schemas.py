from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ChatBase(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ChatCreate(ChatBase):
    pass


class ChatUpdate(ChatBase):
    pass


class ChatListResponse(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None  
    
    model_config = ConfigDict(from_attributes=True)


class ChatBaseResponse(BaseModel):
    id: str
    title: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None 
    
    model_config = ConfigDict(from_attributes=True)


class ChatResponse(ChatBaseResponse):
    pass


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[str]] = None
    chat_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChatMessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    context_length: int = Field(default=4096, ge=512, le=32768)
    run_test: bool = False
    fast_mode: bool = False


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[str]] = None
    chat_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)