"""鉴权：读接口本机可用；管理端需要 X-API-Key。"""

from __future__ import annotations

from fastapi import Header, Request

from ac_api.api.errors import ApiError
from ac_api.config import settings, load_config


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or x_api_key not in settings().keys:
        raise ApiError("unauthorized", "缺少或错误的 X-API-Key", status=401)


def require_admin(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    if load_config().auth.admin_localhost_only:
        host = request.client.host if request.client else ""
        if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
            raise ApiError("forbidden", "管理端点仅限本机访问", status=403)
    require_key(x_api_key)
