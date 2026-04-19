import sys
from pathlib import Path

from loguru import logger

from src.core.paths import LOGS_DIR


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

    if log_file:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(LOGS_DIR / log_file, rotation="10 MB", retention="30 days", level=level)


def get_logger(name: str):
    return logger.bind(module=name)
