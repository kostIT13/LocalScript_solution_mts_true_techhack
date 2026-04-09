from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class RAGChunk(BaseModel):
    content: str = Field(..., description="Текст чанка")
    filename: str = Field(..., description="Имя исходного файла")
    source: str = Field(default="", description="Источник документа")
    chunk_index: int = Field(default=0, description="Индекс чанка в документе")
    score: float = Field(default=0.0, description="Релевантность (0-1)")
    metadata: dict = Field(default_factory=dict, description="Доп. метаданные")
    
    model_config = ConfigDict(from_attributes=True, extra="allow")