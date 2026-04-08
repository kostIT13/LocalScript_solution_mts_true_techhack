from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path  


class Settings(BaseSettings):
    DATABASE_URL: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_MODEL: str = "qwen2.5-coder:1.5b"
    SECRET_KEY: str = "v8Yxl3MvuSevxhmPeLe2unTojoeW9w02f9l0OTiO4bw"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENVIRONMENT: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent.parent / ".env",
                                              
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()