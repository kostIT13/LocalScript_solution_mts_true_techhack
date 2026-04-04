from fastapi import FastAPI
import logging
from src.core.logging_settings import setup_logging
from contextlib import asynccontextmanager
from src.core.database import engine
from sqlalchemy import text
from src.core.config import settings


setup_logging(level=settings.LOG_LEVEL)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Приложение запущено")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Ошибка подключения к бд:{e}")
    yield
    
    await engine.dispose() 
    logger.info("Готово")


app = FastAPI(title="LocalScript", lifespan=lifespan, description="AI-агент для генерации Lua-кода", debug=settings.DEBUG)