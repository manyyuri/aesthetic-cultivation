"""单行 JSON 日志。不打 chunk 全文、不打 key、用户输入截断。"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        for key in ("request_id", "run_id", "domain", "issue_id", "event_name"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        rid = payload.get("request_id") or request_id_var.get()
        if rid:
            payload["request_id"] = rid
        rid2 = payload.get("run_id") or run_id_var.get()
        if rid2:
            payload["run_id"] = rid2
        extra = getattr(record, "data", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)[:2000]
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "ac") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def redact(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    return value[:keep] + "***"


def truncate(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else value[:limit] + "…"
