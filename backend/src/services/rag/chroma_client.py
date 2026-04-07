import logging
import chromadb
from chromadb.config import Settings
from src.core.config import settings


logger = logging.getLogger(__name__)


def _create_chroma_client():
    is_production = settings.ENVIRONMENT == "production"
    
    chroma_settings = Settings(anonymized_telemetry=False)
    
    if is_production:
        logger.info("ChromaDB: режим production, локальное хранилище")
        return chromadb.PersistentClient(
            path="/app/chroma_data",
            settings=chroma_settings
        )
    else:
        logger.info(f"ChromaDB: режим dev, подключение к {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
        return chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=chroma_settings
        )


class ChromaClient:
    def __init__(self, client=None):
        self.client = client or _create_chroma_client()
        self.collection_name = "corpknow_documents"
        
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Коллекция ChromaDB '{self.collection_name}' готова")
        except Exception as e:
            logger.error(f"Ошибка создания коллекции: {e}")
            raise
    
    def get_collection(self):
        return self.collection
    
    def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict]
    ):
        if not ids:
            return
        
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Добавлено {len(ids)} чанков в ChromaDB")
        except Exception as e:
            logger.error(f"Ошибка добавления в Chroma: {e}")
            raise
    
    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        user_id: str = None,
        document_id: str = None
    ):
        try:
            where_filter = {}
            if user_id:
                where_filter["user_id"] = user_id
            if document_id:
                where_filter["document_id"] = document_id
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"]
            )
            return results
        except Exception as e:
            logger.error(f"Ошибка поиска в Chroma: {e}")
            raise
    
    def delete_by_filter(self, user_id: str = None, document_id: str = None):
        try:
            where_filter = {}
            if user_id:
                where_filter["user_id"] = user_id
            if document_id:
                where_filter["document_id"] = document_id
            
            if where_filter:
                deleted = self.collection.delete(where=where_filter)
                logger.info(f"Удалено чанков из Chroma: {len(deleted) if deleted else 0}")
                return deleted
            return []
        except Exception as e:
            logger.error(f"Ошибка удаления из Chroma: {e}")
            raise


_chroma_instance = None

def _get_chroma_instance():
    global _chroma_instance
    if _chroma_instance is None:
        _chroma_instance = ChromaClient()
    return _chroma_instance


class _LazyChromaClient:
    def __getattr__(self, name):
        instance = _get_chroma_instance()
        return getattr(instance, name)


chroma_client = _LazyChromaClient()