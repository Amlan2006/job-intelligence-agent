import json
import logging
import re
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def __init__(self, secrets=()):
        super().__init__()
        self.secrets = tuple(s for s in secrets if s)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "metadata", {}))
        rendered = json.dumps(payload, default=str)
        rendered = re.sub(r"(https://pro-api\.llama\.fi/)[^/\s\"]+", r"\1[REDACTED]", rendered)
        for secret in self.secrets:
            rendered = rendered.replace(secret, "[REDACTED]")
        return rendered


def configure_logging(level: str, secrets=()) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter(secrets))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
