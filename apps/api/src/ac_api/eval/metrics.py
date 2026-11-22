"""检索与内容指标。免 LLM 的三项可进 CI。"""

from __future__ import annotations

import re

CITE_RE = re.compile(r"\[(S\d+)\]")


def recall_at_k(retrieved_docs: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    top = set(retrieved_docs[:k])
    return 1.0 if any(doc in top for doc in expected) else 0.0


def reciprocal_rank(retrieved_docs: list[str], expected: list[str]) -> float:
    for rank, doc in enumerate(retrieved_docs, start=1):
        if doc in expected:
            return 1.0 / rank
    return 0.0


def citation_coverage(answer: str, valid_ids: set[str]) -> float:
    sentences = [s for s in re.split(r"(?<=[。！？\n])", answer) if s.strip()]
    if not sentences:
        return 0.0
    ok = 0
    for sentence in sentences:
        cites = CITE_RE.findall(sentence)
        if cites and all(c in valid_ids for c in cites):
            ok += 1
    return ok / len(sentences)


def refused(answer: str, key_facts: list[str]) -> bool:
    """判"是否拒答"：明确说没资料，且没有抛出任何关键事实。"""
    markers = ("资料里没有", "无法确认", "没有能支撑", "资料不足", "查不到")
    says_no = any(m in answer for m in markers)
    leaks = any(fact and fact in answer for fact in key_facts)
    return says_no and not leaks
