"""Fetcher 公共设施：限速 + 重试 + 响应缓存 + 唯一的落盘校验口。

三条纪律：
1. 任何 fetcher 都不许自己 open(..., "w")，落盘只能走 write_doc；
2. license / source_url / require_meta / 段落长度 全部在 write_doc 里校验；
3. 响应写缓存，重跑不打网络，测试可离线重放。
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from ac_api.config import data_dir, raw_dir
from ac_api.sources import SourceSpec, allowed_licenses, normalize_license, user_agent

MIN_SECTION_CHARS = 40
DOC_ID_RE = re.compile(r"[^a-z0-9_-]+")


class SourceError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class LicenseRefused(SourceError):
    pass


class MissingMeta(SourceError):
    pass


class RetryableHttpError(Exception):
    pass


class RefusedItem(BaseModel):
    external_id: str
    reason: str


class WrittenDoc(BaseModel):
    doc_id: str
    path: str
    text: str = ""
    dry_run: bool = False
    changed: bool = False


class FetchReport(BaseModel):
    source: str
    domain: str
    candidates: int = 0
    written: int = 0
    skipped: int = 0
    dry_run: bool = False
    refused: list[RefusedItem] = Field(default_factory=list)
    missing_meta: dict[str, int] = Field(default_factory=dict)
    preview: list[dict] = Field(default_factory=list)

    def refuse(self, external_id: str | int, reason: str) -> None:
        self.refused.append(RefusedItem(external_id=str(external_id), reason=reason))
        if reason.startswith("missing_meta:"):
            key = reason.split(":", 1)[1]
            self.missing_meta[key] = self.missing_meta.get(key, 0) + 1


class Fetcher(Protocol):
    spec: SourceSpec

    def fetch(self, limit: int, query: str | None = None, dry_run: bool = False) -> FetchReport: ...


def doc_id_for(source: str, external_id: str | int) -> str:
    slug = DOC_ID_RE.sub("-", str(external_id).lower()).strip("-")
    return f"{source}_{slug}"[:80]


def _cache_path(spec: SourceSpec, key: str) -> Path:
    safe = DOC_ID_RE.sub("-", key).strip("-")[:120]
    path = data_dir() / "cache" / "sources" / spec.name
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{safe}.json"


class Http:
    """按源限速的 HTTP 客户端；GET 结果写缓存，重跑不打网络。"""

    def __init__(self, spec: SourceSpec, client: httpx.Client | None = None, use_cache: bool = True) -> None:
        self.spec = spec
        self._client = client or httpx.Client(
            timeout=20,
            headers={"User-Agent": user_agent(spec), "Accept": "application/json,text/plain,*/*"},
        )
        self._interval = 1.0 / max(spec.rate_limit_rps, 0.1)
        self._last = 0.0
        self.use_cache = use_cache

    def _throttle(self) -> None:
        wait = self._interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=0.5, max=6),
        retry=retry_if_exception_type(RetryableHttpError),
        reraise=True,
    )
    def _get(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        self._throttle()
        try:
            resp = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise RetryableHttpError(str(exc)) from exc
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableHttpError(f"HTTP {resp.status_code} {url}")
        if resp.status_code >= 400:
            raise SourceError("http_error", f"HTTP {resp.status_code}：{url}", {"body": resp.text[:200]})
        return resp

    def get_json(self, url: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> dict:
        path = _cache_path(self.spec, cache_key or url)
        if self.use_cache and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self._get(url, params).json()
        if self.use_cache:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def get_text(self, url: str, cache_key: str | None = None) -> str:
        path = _cache_path(self.spec, (cache_key or url) + ".txt")
        if self.use_cache and path.exists():
            return path.read_text(encoding="utf-8")
        text = self._get(url, None).text
        if self.use_cache:
            path.write_text(text, encoding="utf-8")
        return text


def _body_sections(body: str) -> list[str]:
    parts = re.split(r"^##\s+", body, flags=re.M)
    if len(parts) <= 1:
        return [body]
    return [part.split("\n", 1)[1] if "\n" in part else part for part in parts[1:]]


def validate_body(body: str) -> None:
    for section in _body_sections(body):
        if len(section.strip()) < MIN_SECTION_CHARS:
            raise SourceError(
                "body_too_short",
                f"有段落短于 {MIN_SECTION_CHARS} 字，入库会被 too_short 拒",
                {"length": len(section.strip())},
            )


def write_doc(
    spec: SourceSpec,
    *,
    external_id: str | int,
    title: str,
    body: str,
    meta: dict[str, Any],
    source_url: str,
    license_id: str | None = None,
    source_priority: str | None = None,
    retrieved_at: str | None = None,
    dry_run: bool = False,
) -> WrittenDoc:
    """唯一落盘口。校验不过就抛，不产生任何文件。"""
    license_text = normalize_license(license_id or spec.license)
    if not license_text or license_text not in allowed_licenses():
        raise LicenseRefused(
            "license_refused",
            f"license 不在白名单：{license_id or spec.license}",
            {"allowed": allowed_licenses()},
        )
    if not source_url:
        raise LicenseRefused("missing_source_url", "缺 source_url，展签将无法核查")

    missing = [key for key in spec.require_meta if meta.get(key) in (None, "")]
    if missing:
        raise MissingMeta(
            "missing_meta:" + ",".join(missing), f"缺必填元数据：{missing}", {"missing": missing}
        )
    validate_body(body)

    doc_id = doc_id_for(spec.name, external_id)
    front = {
        "doc_id": doc_id,
        "domain": spec.domain,
        "title": title,
        "source": spec.name,
        "external_id": str(external_id),
        "source_url": source_url,
        "license": license_text,
        "source_priority": source_priority or spec.source_priority,
        "retrieved_at": retrieved_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "meta": meta,
    }
    lines = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items())
    text = f"---\n{lines}\n---\n\n{body.strip()}\n"

    path = raw_dir(spec.domain) / f"{doc_id}.md"
    if dry_run:
        return WrittenDoc(doc_id=doc_id, path=str(path), text=text, dry_run=True, changed=False)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return WrittenDoc(doc_id=doc_id, path=str(path), text=text, dry_run=False, changed=False)
    path.write_text(text, encoding="utf-8")
    return WrittenDoc(doc_id=doc_id, path=str(path), text=text, dry_run=False, changed=True)


def mmss(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
