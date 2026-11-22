"""分块公共能力：协议 + 段落窗口 + 中文数字。禁止在调用方写 if domain。"""

from __future__ import annotations

import re
from typing import Protocol

from ac_api.config import DomainSpec
from ac_api.domain.models import ChunkDraft, estimate_tokens
from ac_api.rag.ingest.loaders.md import LoadedDoc, Section

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
TARGET_TOKENS = 420
MIN_TOKENS = 80
MAX_TOKENS = 620
OVERLAP_TOKENS = 60


class Chunker(Protocol):
    name: str

    def split(self, doc: LoadedDoc, spec: DomainSpec) -> list[ChunkDraft]: ...


def cn_number(token: str) -> int | None:
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token in CN_NUM:
        return CN_NUM[token]
    if token.startswith("十") and len(token) == 2 and token[1] in CN_NUM:
        return 10 + CN_NUM[token[1]]
    if len(token) == 2 and token[0] in CN_NUM and token[1] == "十":
        return CN_NUM[token[0]] * 10
    return None


def window_section(section: Section) -> list[str]:
    """按段落切窗：只在同一小节内 overlap，跨小节绝不重叠。"""
    text = section.text
    if estimate_tokens(text) <= MAX_TOKENS:
        return [text] if text else []
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    windows: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for para in paras:
        pt = estimate_tokens(para)
        if buf and buf_tokens + pt > TARGET_TOKENS:
            windows.append("\n\n".join(buf))
            tail = buf[-1]
            buf = [tail] if estimate_tokens(tail) <= OVERLAP_TOKENS else []
            buf_tokens = estimate_tokens(tail) if buf else 0
        buf.append(para)
        buf_tokens += pt
    if buf:
        windows.append("\n\n".join(buf))
    return [w for w in windows if estimate_tokens(w) >= MIN_TOKENS] or [text]


def build_drafts(
    doc: LoadedDoc,
    section: Section,
    *,
    metadata: dict,
    parent_heading: str | None,
    domain: str,
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for piece in window_section(section):
        drafts.append(
            ChunkDraft(
                doc_id=doc.doc_id,
                domain=domain,
                text=piece,
                heading=section.heading or doc.title,
                parent_heading=parent_heading,
                metadata=dict(metadata),
                page=None,
            )
        )
    return drafts
