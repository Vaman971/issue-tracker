import json
import logging
import sys
from datetime import datetime, timezone

from app.core.log_filters import RequestIdFilter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # structured payloads passed as extra={"telemetry": {...}} are nested
        # as an object rather than flattened into the message string
        telemetry = getattr(record, "telemetry", None)
        if telemetry:
            log_data["telemetry"] = telemetry

        return json.dumps(log_data)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
