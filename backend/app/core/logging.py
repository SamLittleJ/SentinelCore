import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# Set per request by the request middleware, so every log line written while
# handling a request carries its id.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes present on every LogRecord; anything else was passed via `extra`.
_STANDARD_RECORD_ATTRIBUTES = set(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None))
) | {"message", "asctime", "taskName"}


def _extra_fields(record: logging.LogRecord) -> dict[str, object]:
    return {
        key: value
        for key, value in vars(record).items()
        if key not in _STANDARD_RECORD_ATTRIBUTES
    }


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log collectors."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id is not None:
            entry["request_id"] = request_id

        entry.update(_extra_fields(record))

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable lines for local development, with the same fields."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).strftime("%H:%M:%S")
        request_id = request_id_var.get() or "-"
        fields = " ".join(
            f"{key}={value}" for key, value in _extra_fields(record).items()
        )
        line = (
            f"{timestamp} {record.levelname:<7} [{request_id}] "
            f"{record.name}: {record.getMessage()}"
        )
        if fields:
            line = f"{line} {fields}"
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(level: str, log_format: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log_format == "json" else TextFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Route uvicorn's own logs through the same handler and format.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # The request middleware writes one structured line per request, so
    # uvicorn's access log would only duplicate it.
    logging.getLogger("uvicorn.access").disabled = True
