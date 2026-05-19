"""日志配置"""

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    log_format: str = "console",
) -> None:
    """配置日志系统（structlog）

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为 None 则只输出到控制台
        log_format: 输出格式，"console" 为人类可读，"json" 为结构化 JSON
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # --- stdlib handlers ---
    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # 降低第三方库噪音
    for noisy in ("httpx", "httpcore", "openai", "langchain"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # --- structlog processors ---
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    for handler in handlers:
        handler.setFormatter(formatter)
