import logging
from pathlib import Path
from typing import List, Optional
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredMarkdownLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangChainDocument

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=self.separators,
            is_separator_regex=False,
        )
        logger.info(f"DocumentProcessor инициализирован (chunk_size={chunk_size})")
    
    def _get_loader(self, file_path: str, file_type: str):
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        loaders = {
            "application/pdf": lambda: PyPDFLoader(str(path)),
            "text/plain": lambda: TextLoader(str(path), encoding="utf-8", autodetect_encoding=True),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 
                lambda: Docx2txtLoader(str(path)),
            "text/markdown": lambda: UnstructuredMarkdownLoader(str(path)),
            "text/x-markdown": lambda: UnstructuredMarkdownLoader(str(path)),
        }
        
        loader_factory = loaders.get(file_type)
        if not loader_factory:
            ext = path.suffix.lower()
            fallback = {
                ".pdf": PyPDFLoader,
                ".txt": TextLoader,
                ".docx": Docx2txtLoader,
                ".md": UnstructuredMarkdownLoader,
                ".markdown": UnstructuredMarkdownLoader,
            }
            if ext in fallback:
                logger.warning(f"MIME-тип {file_type} неизвестен, использую расширение {ext}")
                return fallback[ext](str(path))
            raise ValueError(f"Неподдерживаемый тип файла: {file_type} ({ext})")
        
        return loader_factory()
    
    def load_document(self, file_path: str, file_type: str) -> List[LangChainDocument]:
        try:
            loader = self._get_loader(file_path, file_type)
            documents = loader.load()
            
            for doc in documents:
                doc.metadata = {
                    "source": file_path,
                    "page": doc.metadata.get("page", 0),
                    "filename": Path(file_path).name
                }
            
            logger.info(f"Загружено {len(documents)} страниц из {Path(file_path).name}")
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_path}: {e}")
            raise
    
    def split_documents(self, documents: List[LangChainDocument]) -> List[LangChainDocument]:
        if not documents:
            return []
        
        chunks = self.text_splitter.split_documents(documents)
        
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(chunks)
        
        logger.info(f"Разбито на {len(chunks)} чанков")
        return chunks
    
    def process(self, file_path: str, file_type: str) -> List[LangChainDocument]:
        try:
            documents = self.load_document(file_path, file_type)
            if not documents:
                raise ValueError("Документ пуст или не содержит текста")
            
            chunks = self.split_documents(documents)
            if not chunks:
                raise ValueError("Не удалось разбить документ на чанки")
            
            logger.info(f"Обработан {Path(file_path).name}: {len(chunks)} чанков")
            return chunks
            
        except Exception as e:
            logger.error(f"Ошибка обработки {file_path}: {e}")
            raise
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4


document_processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)