"""FastAPI 装配：中间件、异常映射、路由挂载。"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ac_api import __version__
from ac_api.api.errors import ApiError, install_exception_handlers
from ac_api.api.routes_eval import router as eval_router
from ac_api.api.routes_health import router as health_router
from ac_api.api.routes_issues import router as issues_router
from ac_api.api.routes_items import router as items_router
from ac_api.api.routes_kb import router as kb_router
from ac_api.api.routes_media import router as media_router
from ac_api.api.routes_subs import router as subs_router
from ac_api.obs.logger import get_logger, request_id_var
from ac_api.obs.metrics import metrics
from ac_api.store.db import init_db

log = get_logger("http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("app_start", extra={"data": {"version": __version__}})
    yield
    log.info("app_stop")


app = FastAPI(
    title="aesthetic-cultivation",
    version=__version__,
    description="私人节目单：每天/每周一期，三幕、带出处。",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or f"r_{uuid.uuid4().hex[:12]}"
    token = request_id_var.set(rid)
    started = time.monotonic()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    elapsed = (time.monotonic() - started) * 1000
    response.headers["X-Request-Id"] = rid
    metrics.observe("http_request_duration_seconds", elapsed / 1000, {"path": request.url.path})
    log.info(
        "request",
        extra={
            "request_id": rid,
            "data": {"path": request.url.path, "status": response.status_code, "ms": int(elapsed)},
        },
    )
    return response


@app.get("/metrics", include_in_schema=False)
def prometheus() -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


install_exception_handlers(app)
app.include_router(health_router)
app.include_router(issues_router)
app.include_router(items_router)
app.include_router(kb_router)
app.include_router(media_router)
app.include_router(subs_router)
app.include_router(eval_router)
