import logging
import os
import threading
import contextvars
from datetime import datetime
from typing import Dict, Any

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_LOGGER_CACHE: Dict[str, logging.Logger] = {}
_LOGGER_CONTEXT = contextvars.ContextVar("logger_name", default="mynamechat")

def set_logger_context(name: str):
    """Set the logger name for the current context."""
    _LOGGER_CONTEXT.set(name)

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
    
    日志级别通过环境变量 LOG_LEVEL 控制，默认为 INFO。
    设置 LOG_LEVEL=DEBUG 可以看到 debug 级别的日志。
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    log_path = _build_log_path()
    logger = logging.getLogger(name)
    
    # 从环境变量读取日志级别，默认 INFO
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

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

class LoggerProxy:
    """
    A proxy that delegates calls to the logger defined in the current context.
    """
    def __getattr__(self, name: str) -> Any:
        current_name = _LOGGER_CONTEXT.get()
        # Ensure we're using a logger specific to the context, or default
        real_logger = get_logger(current_name)
        return getattr(real_logger, name)

# Export a global proxy that tools can use
logger_proxy = LoggerProxy()

def write_test_log(content: str, logger: logging.Logger | None = None) -> None:
    """
    Backwards-compatible helper for ad-hoc logging during tests.
    """
    logger = logger or get_logger("mynamechat.test")
    logger.info(content)

