import json
import logging
import time
import uuid

from fastapi import FastAPI, Request

logger = logging.getLogger("streamsaathi")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "msg": record.getMessage(), "logger": record.name}
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("streamsaathi")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False


def log_event(msg: str, **fields) -> None:
    logger.info(msg, extra={"extra_fields": fields})


def add_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log_event(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            user_id=getattr(request.state, "user_id", None),
        )
        return response
