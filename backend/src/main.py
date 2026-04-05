from fastapi import FastAPI
import logging
from src.core.logging_settings import setup_logging
from contextlib import asynccontextmanager
from src.core.database import engine
from sqlalchemy import text
from src.core.config import settings
from src.models.generation import CodeGeneration
from src.models.user import User
from src.api.generate.endpoints import router as generate_router
from src.api.history.endpoints import router as history_router


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

app.include_router(generate_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")