"""
app/core/logging.py
────────────────────
Structured JSON logging setup.
"""
import logging
import sys
from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # JSON-friendly format for cloud log aggregators (CloudWatch, GCP Logging, etc.)
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        if settings.APP_ENV == "development"
        else '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [handler]

    # Silence noisy third-party loggers
    for noisy in ("sqlalchemy.engine", "httpx", "celery.utils.functional", "uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
