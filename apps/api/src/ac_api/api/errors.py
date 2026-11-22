"""统一错误信封 + 单一异常映射。禁止每个路由自己拼 try/except 响应。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ac_api.config import UnknownDomain
from ac_api.obs.logger import get_logger, request_id_var
from ac_api.rag.index.builder import NoChunks
from ac_api.rag.retrieve.filters import FilterError
from ac_api.rag.retrieve.pipeline import RetrieveError
from ac_api.store.issues import AlreadyDelivered

log = get_logger("error")


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
        self.retryable = retryable


def envelope(code: str, message: str, details: dict | None = None, retryable: bool = False) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}, "retryable": retryable}}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "retryable": exc.retryable,
                },
                "request_id": request_id_var.get(),
            },
        )

    @app.exception_handler(UnknownDomain)
    async def _unknown_domain(request: Request, exc: UnknownDomain):
        return JSONResponse(
            status_code=400,
            content=envelope("invalid_domain", str(exc), {"domain": exc.domain}, False),
        )

    @app.exception_handler(FilterError)
    async def _filter_error(request: Request, exc: FilterError):
        return JSONResponse(status_code=400, content=envelope("invalid_filter", str(exc), exc.details, False))

    @app.exception_handler(RetrieveError)
    async def _retrieve_error(request: Request, exc: RetrieveError):
        status = 400 if exc.code in ("empty_query", "query_too_long") else 500
        return JSONResponse(status_code=status, content=envelope(exc.code, exc.message, exc.details, False))

    @app.exception_handler(NoChunks)
    async def _no_chunks(request: Request, exc: NoChunks):
        return JSONResponse(
            status_code=503,
            content=envelope(
                "index_unavailable",
                str(exc),
                {"hint": "先跑 make ingest DOMAIN=… && make index DOMAIN=…"},
                True,
            ),
        )

    @app.exception_handler(AlreadyDelivered)
    async def _already(request: Request, exc: AlreadyDelivered):
        return JSONResponse(status_code=409, content=envelope("issue_already_delivered", str(exc), {}, False))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=envelope("invalid_request", "请求体不合法", {"errors": exc.errors()[:5]}, False),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.info("unhandled", extra={"data": {"path": request.url.path, "error": str(exc)[:400]}})
        return JSONResponse(
            status_code=500,
            content=envelope("internal", "服务内部错误", {"request_id": request_id_var.get()}, True),
        )
