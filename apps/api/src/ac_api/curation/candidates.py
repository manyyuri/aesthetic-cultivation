"""选题：候选只能来自库内真实对象（必带 doc_id）。话题不许由模型凭空想。"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date

from pydantic import BaseModel, Field

from ac_api.config import DomainSpec, load_config
from ac_api.domain.models import Chunk
from ac_api.rag.ingest.pipeline import load_chunks

TITLE_SUFFIXES = ("著录", "档案", "演出记录", "首演记录", "出版著录", "记录")


class Candidate(BaseModel):
    key: str
    domain: str
    doc_id: str
    title_zh: str
    title_orig: str | None = None
    heading: str | None = None
    text: str
    chunks: list[Chunk] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    rank_score: float = 0.0
    source_priority: str = "secondary_web"
    reasons: list[str] = Field(default_factory=list)


def _clean_title(title: str, meta: dict) -> str:
    if meta.get("display_zh"):
        return str(meta["display_zh"])
    for suffix in TITLE_SUFFIXES:
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return title.strip()


def _anniversary(year: int | None, publish: date) -> float:
    if not year:
        return 0.0
    delta = publish.year - int(year)
    if delta <= 0:
        return 0.0
    if delta % 10 == 0:
        return 1.0
    if delta % 5 == 0:
        return 0.7
    if delta % 1 == 0:
        return 0.3
    return 0.0


def _jitter(key: str, publish: str) -> float:
    digest = hashlib.blake2b(f"{publish}:{key}".encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big") / 0xFFFFFFFF


def build_candidates(
    domain: str,
    publish_date: str,
    *,
    limit: int = 8,
    used_docs: dict[str, str] | None = None,
    used_keys: set[str] | None = None,
    no_repeat_doc_days: int = 14,
    no_repeat_item_days: int = 90,
) -> list[Candidate]:
    spec = load_config().domain(domain)
    publish = date.fromisoformat(publish_date)
    by_doc: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in load_chunks(domain):
        by_doc[chunk.doc_id].append(chunk)

    used_docs = used_docs or {}
    used_keys = used_keys or set()
    out: list[Candidate] = []
    for doc_id, chunks in by_doc.items():
        chunks.sort(key=lambda c: c.chunk_id)
        meta = dict(chunks[0].metadata)
        title_zh = _clean_title(chunks[0].locator.doc_title, meta)
        title_orig = meta.get("title_orig") or meta.get("work")
        key = f"{domain}:{title_orig or title_zh}"
        reasons: list[str] = []
        if key in used_keys:
            reasons.append(f"近 {no_repeat_item_days} 天推过")
        last = used_docs.get(doc_id)
        if last:
            gap = (publish - date.fromisoformat(last)).days
            if gap < no_repeat_doc_days:
                reasons.append(f"同文档 {gap} 天内用过")
        year = meta.get("premiere_year") or meta.get("release_year")
        anniversary = _anniversary(year if isinstance(year, int) else None, publish)
        completeness = sum(1 for k in spec.required_meta if meta.get(k)) / max(len(spec.required_meta), 1)
        novelty = 1.0 if not last else min(1.0, (publish - date.fromisoformat(last)).days / 90)
        score = 0.4 * anniversary + 0.3 * novelty + 0.2 * completeness + 0.1 * _jitter(doc_id, publish_date)
        text = "\n\n".join(c.text for c in chunks[:3])
        out.append(
            Candidate(
                key=key,
                domain=domain,
                doc_id=doc_id,
                title_zh=title_zh,
                title_orig=str(title_orig) if title_orig else None,
                heading=chunks[0].locator.anchor,
                text=text,
                chunks=chunks,
                metadata=meta,
                rank_score=round(score, 4),
                source_priority=chunks[0].source_priority,
                reasons=reasons,
            )
        )
    usable = [c for c in out if not c.reasons]
    usable.sort(key=lambda c: -c.rank_score)
    return usable[:limit]


def candidate_spec(domain: str) -> DomainSpec:
    return load_config().domain(domain)
