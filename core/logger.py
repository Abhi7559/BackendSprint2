import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

# Context variable holding the request_id for the current asyncio task/request
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")


def get_request_id() -> str:
    """Return the request_id from context or empty string."""
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request_id for the current context."""
    request_id_ctx.set(request_id)


class JSONFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects with:
    level, timestamp, logger, message, request_id
    """
    def format(self, record: logging.LogRecord) -> str:
        # Check if record has explicit request_id or use context var
        req_id = getattr(record, "request_id", None) or get_request_id()

        log_data = {
            "level": record.levelname,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": req_id,
        }

        # If exception info is present, include it in message or detail
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with the structured JSONFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
