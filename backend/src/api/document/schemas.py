from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from src.models.document import DocumentStatus  


class DocumentListResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: Optional[str] = None
    status: DocumentStatus  
    chunk_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None  
    
    model_config = ConfigDict(from_attributes=True)  


class DocumentResponse(DocumentListResponse):
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    user_id: str  
    
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: DocumentStatus 
    message: str = "Документ загружен и обрабатывается"
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListWithPagination(BaseModel):
    items: List[DocumentListResponse]
    total: int
    page: int = 1
    page_size: int = 10