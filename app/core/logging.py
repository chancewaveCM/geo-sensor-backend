"""
Structured Logging Module
F14: PM2-compatible structured logging with correlation IDs
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any

# Correlation ID for request tracing
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add correlation ID if set
        cid = correlation_id_var.get()
        if cid:
            log_data['correlation_id'] = cid

        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra data if present
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data['extra'] = record.extra_data

        # Add standard fields
        log_data['module'] = record.module
        log_data['function'] = record.funcName
        log_data['line'] = record.lineno

        return json.dumps(log_data, default=str)


class StandardFormatter(logging.Formatter):
    """Standard human-readable formatter"""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record: logging.LogRecord) -> str:
        # Prepend correlation ID if set
        cid = correlation_id_var.get()
        if cid:
            record.msg = f"[{cid}] {record.msg}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """
    Configure application logging

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format (True) or human-readable (False)
        log_file: Optional file path for logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = JSONFormatter() if json_format else StandardFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def generate_correlation_id() -> str:
    """Generate a new correlation ID (8-char UUID prefix)"""
    return str(uuid.uuid4())[:8]


def set_correlation_id(cid: str | None = None) -> str:
    """
    Set correlation ID for current context

    Args:
        cid: Optional specific correlation ID, generates new if None

    Returns:
        The correlation ID that was set
    """
    cid = cid or generate_correlation_id()
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str:
    """Get current correlation ID"""
    return correlation_id_var.get()


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that automatically includes extra data"""

    def process(self, msg: str, kwargs: dict) -> tuple:
        extra = kwargs.get('extra', {})
        extra['extra_data'] = self.extra
        kwargs['extra'] = extra
        return msg, kwargs


def get_logger_with_context(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with automatic context injection

    Args:
        name: Logger name
        **context: Key-value pairs to include in all log messages

    Returns:
        LoggerAdapter that includes context
    """
    return LoggerAdapter(get_logger(name), context)
