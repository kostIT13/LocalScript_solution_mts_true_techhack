import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_str: Optional[str] = None,
) -> None:
    if format_str is None:
        format_str = "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8", mode="a"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True, 
    )
    
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    
    logging.getLogger(__name__).info(f"Логирование настроено (уровень: {level})")