import logging
import os
import threading
from datetime import datetime
from typing import Dict

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_LOGGER_CACHE: Dict[str, logging.Logger] = {}


def _build_log_path() -> str:
    """Create a log file path that follows <timestamp>_<thread_id>.log."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    thread_id = threading.get_ident()
    file_name = f"{timestamp}_{thread_id}.log"
    return os.path.join(LOG_DIR, file_name)


def get_logger(name: str = "mynamechat") -> logging.Logger:
    """
    Return a configured logger that writes to both console and file.
    Each logger name is cached to avoid duplicate handlers.
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    log_path = _build_log_path()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s - %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # 防止重复添加
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.propagate = False
        logger.info("Logger initialized. Writing to %s", log_path)

    _LOGGER_CACHE[name] = logger
    return logger


def write_test_log(content: str, logger: logging.Logger | None = None) -> None:
    """
    Backwards-compatible helper for ad-hoc logging during tests.
    """
    logger = logger or get_logger("mynamechat.test")
    logger.info(content)

