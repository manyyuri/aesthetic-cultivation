"""全仓库唯一事实来源的数据结构。落盘 JSON 与 API 字段同名。"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AnchorKind = Literal["listen", "watch", "look"]
EvidenceStatus = Literal["found", "weak", "insufficient"]


def normalize_text(text: str) -> str:
    # NFC 而不是 NFKC：NFKC 会把中文全角标点（，。：）压成半角，展签排版会立刻变味
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:32]


def estimate_tokens(text: str) -> int:
    """中文按字符、西文按 4 字符 ≈ 1 token 的粗略估算（只用于预算与切块，不做计费）。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    rest = len(text) - cjk
    return cjk + max(1, rest // 4)


class Locator(BaseModel):
    doc_title: str
    page: int | None = None
    anchor: str | None = None
    url: str | None = None

    def as_citation(self) -> str:
        bits = [self.doc_title]
        if self.anchor:
            bits.append(self.anchor)
        if self.page:
            bits.append(f"p.{self.page}")
        return " · ".join(bits)


class ChunkDraft(BaseModel):
    doc_id: str
    domain: str
    text: str
    heading: str
    parent_heading: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    page: int | None = None
    ordinal: int = 0


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    domain: str
    index_version: str = "dev"
    text: str
    parent_id: str | None = None
    locator: Locator
    metadata: dict[str, Any] = Field(default_factory=dict)
    tokens: int = 0
    content_hash: str = ""
    source_priority: str = "secondary_web"
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def finalize(self) -> Chunk:
        self.text = normalize_text(self.text)
        self.tokens = estimate_tokens(self.text)
        self.content_hash = content_hash(self.text)
        return self


class Anchor(BaseModel):
    kind: AnchorKind
    label: str
    spec: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    mark: str
    chunk_id: str
    doc_id: str
    source: str
    excerpt: str
    scores: dict[str, float] = Field(default_factory=dict)


class MetaLine(BaseModel):
    k: str
    v: str


class Item(BaseModel):
    id: str
    issue_id: str
    ord: int
    domain: str
    title_zh: str
    title_orig: str | None = None
    meta_lines: list[MetaLine] = Field(default_factory=list)
    hook: str
    anchor: Anchor
    evidence: list[Evidence] = Field(default_factory=list)
    image_url: str | None = None
    done_at: datetime | None = None
    rank_score: float = 0.0


class Issue(BaseModel):
    id: str
    kind: Literal["daily", "weekly"] = "daily"
    issue_no: int
    publish_date: str
    title: str
    subtitle: str
    minutes: int
    status: Literal["draft", "ready", "delivered", "partial"] = "draft"
    generated_at: datetime | None = None
    delivered_at: datetime | None = None
    items: list[Item] = Field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.done_at)


class RetrieveRequest(BaseModel):
    domain: str
    query: str
    top_k: int = 4
    meta_filter: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None


class RetrievedChunk(BaseModel):
    citation_id: str
    chunk_id: str
    content: str
    context_prefix: str | None = None
    source: str
    locator: Locator
    doc_id: str
    domain: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)
    source_priority: str = "secondary_web"


class RetrieveResponse(BaseModel):
    request_id: str
    domain: str
    index_version: str
    evidence_status: EvidenceStatus
    latency_ms: int
    cache_hit: bool = False
    cache_scope: str | None = None
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    missing_hint: str | None = None
    suggested_queries: list[str] = Field(default_factory=list)
