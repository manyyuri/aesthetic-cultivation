"""媒体代理：把远程图缓到本地再给浏览器。

为什么不让前端直接 <img src="https://images.metmuseum.org/...">：
实测浏览器取图会 403（curl 却 200），热链不稳定；而且图挂了展签就空了。
代理后：只允许 sources.yaml 里声明的域名（防 SSRF），缓存到 data/media，离线也能看。
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ac_api.config import data_dir
from ac_api.obs.logger import get_logger
from ac_api.sources import allowed_media_hosts, sources, user_agent

router = APIRouter(prefix="/api", tags=["media"])
log = get_logger("media")
MAX_BYTES = 8 * 1024 * 1024


def media_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    folder = data_dir() / "media"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / digest


def _validate(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="只代理 https 图片")
    if parsed.hostname not in allowed_media_hosts():
        raise HTTPException(status_code=400, detail=f"域名未授权：{parsed.hostname}")
    return url


@router.get("/media")
def media(src: str = Query(..., max_length=2048)) -> FileResponse:
    url = _validate(src)
    path = media_cache_path(url)
    if not path.exists():
        spec = next((s for s in sources().sources.values() if any(h == urlparse(url).hostname for h in s.media_hosts)), None)
        headers = {"User-Agent": user_agent(spec) if spec else "aesthetic-cultivation/0.1"}
        headers["Referer"] = "https://www.metmuseum.org/"
        try:
            with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.info("media_fetch_failed", extra={"data": {"url": url[:120], "error": str(exc)[:120]}})
            raise HTTPException(status_code=502, detail="取图失败") from exc
        if len(resp.content) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="图片过大")
        path.write_bytes(resp.content)
        path.with_suffix(".type").write_text(
            resp.headers.get("content-type", "image/jpeg"), encoding="utf-8"
        )
    media_type = "image/jpeg"
    type_file = path.with_suffix(".type")
    if type_file.exists():
        media_type = type_file.read_text(encoding="utf-8").strip() or media_type
    if media_type == "image/jpeg" and not Path(url).suffix:
        media_type = mimetypes.guess_type(url)[0] or media_type
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=604800"})
