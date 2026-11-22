"""写作：先规则（可复现、可测试），有 key 时才用 LLM 改写措辞。

硬约束：hook ≤60 字、≤2 句、无营销词/无"据说"、每个事实点必须能在 evidence 原文里找到。
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from pydantic import BaseModel, Field

from ac_api.config import load_config, settings
from ac_api.curation.anchors import mmss
from ac_api.curation.candidates import Candidate
from ac_api.domain.models import Anchor, Chunk, MetaLine
from ac_api.obs.logger import get_logger
from ac_api.rag.index.tokenizer import tokenizer

log = get_logger("write")
SENT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?]?")


class WrittenItem(BaseModel):
    title_zh: str
    title_orig: str | None = None
    meta_lines: list[MetaLine] = Field(default_factory=list)
    hook: str
    anchor: Anchor


class Writer(Protocol):
    name: str

    def write(self, candidate: Candidate, evidence: list[Chunk], anchor: Anchor) -> WrittenItem: ...


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.findall(text) if len(s.strip()) >= 10]


def _rules() -> dict:
    return load_config().curation.get("rules", {})


def _meta_lines(domain: str, meta: dict, anchor: Anchor) -> list[MetaLine]:
    if domain == "art":
        material = " · ".join(x for x in (meta.get("material"), meta.get("technique")) if x)
        return [
            MetaLine(k="材质", v=material or "—"),
            MetaLine(k="年代", v=str(meta.get("period") or "—")),
            MetaLine(k="馆藏", v=str(meta.get("museum") or "—")),
        ]
    if domain == "music":
        duration = meta.get("duration_s")
        length = f"{duration // 60} 分钟" if isinstance(duration, int) else "—"
        movement = anchor.spec.get("movement")
        return [
            MetaLine(k="作曲家", v=str(meta.get("composer") or "—")),
            MetaLine(k="乐章", v=f"第{movement}乐章 · 全曲 {length}" if movement else f"全曲 {length}"),
            MetaLine(k="版本", v=str(meta.get("orchestra") or meta.get("conductor") or "—")),
        ]
    if domain == "ballet":
        year = meta.get("premiere_year")
        company = meta.get("ballet_company") or "—"
        return [
            MetaLine(k="编舞", v=str(meta.get("choreographer") or "—")),
            MetaLine(k="首演", v=f"{year} · {company}" if year else company),
            MetaLine(k="结构", v=f"{meta.get('acts')} 幕" if meta.get("acts") else "—"),
        ]
    return [MetaLine(k=k, v=str(v)) for k, v in list(meta.items())[:3]]


class StubWriter:
    """抽取式写作：句子从 evidence 里选，所以天然不会编。"""

    name = "stub"

    def write(self, candidate: Candidate, evidence: list[Chunk], anchor: Anchor) -> WrittenItem:
        cfg = load_config().curation
        hook_cfg = cfg.get("daily", {}) if candidate.domain else {}
        max_chars = int(hook_cfg.get("hook_max_chars", 60))
        banned = set(_rules().get("marketing_words", [])) | set(_rules().get("hedge_words", []))
        title_tokens = set(tokenizer.tokens(candidate.title_zh + " " + (candidate.title_orig or "")))

        best: tuple[float, str] | None = None
        for chunk in evidence:
            for sentence in _sentences(chunk.text):
                if any(word in sentence for word in banned):
                    continue
                tokens = set(tokenizer.tokens(sentence))
                overlap = len(tokens & title_tokens) / max(len(title_tokens), 1)
                length_penalty = 1.0 if 18 <= len(sentence) <= max_chars * 1.6 else 0.6
                score = overlap + 0.15 * length_penalty
                if best is None or score > best[0]:
                    best = (score, sentence)

        hook = best[1] if best else ""
        if not hook and evidence:
            hook = evidence[0].text[:max_chars]
        hook = _trim(hook, max_chars)
        return WrittenItem(
            title_zh=candidate.title_zh,
            title_orig=candidate.title_orig,
            meta_lines=_meta_lines(candidate.domain, candidate.metadata, anchor),
            hook=hook,
            anchor=anchor,
        )


def _trim(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for mark in ("，", "、", "；", "：", " "):
        idx = cut.rfind(mark)
        if idx >= max_chars * 0.6:
            return cut[:idx] + "…"
    return cut + "…"


class LlmWriter:
    """有 DEEPSEEK_API_KEY 时用它润色措辞；任何异常都退回 StubWriter。"""

    name = "llm"

    def __init__(self) -> None:
        from ac_api.llm.deepseek import DeepSeekClient

        self._client = DeepSeekClient()
        self._stub = StubWriter()
        self._prompt = _read_prompt("writer")

    def write(self, candidate: Candidate, evidence: list[Chunk], anchor: Anchor) -> WrittenItem:
        base = self._stub.write(candidate, evidence, anchor)
        payload = {
            "title_zh": base.title_zh,
            "title_orig": base.title_orig,
            "meta_lines": [m.model_dump() for m in base.meta_lines],
            "hook": base.hook,
            "anchor": anchor.model_dump(),
            "evidence": [c.text[:600] for c in evidence[:3]],
        }
        try:
            data = self._client.json(
                system=self._prompt,
                user=json.dumps(payload, ensure_ascii=False),
                schema=WrittenItem,
                temperature=0.4,
                max_tokens=1500,
            )
            return WrittenItem.model_validate({**base.model_dump(), **data, "anchor": anchor.model_dump()})
        except Exception as exc:  # 任何失败都不影响产期
            log.info("writer_llm_fallback", extra={"data": {"error": str(exc)[:200]}})
            return base


def _read_prompt(name: str) -> str:
    from ac_api.orchestrator.prompts import read_prompt

    return read_prompt(name)


def get_writer() -> Writer:
    if settings().deepseek_api_key and settings().deepseek_model:
        try:
            return LlmWriter()
        except Exception as exc:  # pragma: no cover
            log.info("writer_llm_unavailable", extra={"data": {"error": str(exc)[:200]}})
    return StubWriter()
