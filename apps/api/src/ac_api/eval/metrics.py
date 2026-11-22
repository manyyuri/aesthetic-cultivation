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
    """判"是否拒答"：明确说没资料，且没有把关键事实当成断言写出来。

    只看"带引用的句子"里有没有关键事实——拒答时复述问题里的词（"资料里没有卢浮宫的…"）
    是正常表达，不该算泄漏；只有把它写进带 [S#] 的断言才算编造。
    """
    markers = ("资料里没有", "资料中没有", "无法确认", "无法回答", "没有能支撑", "资料不足", "查不到")
    if not any(m in answer for m in markers):
        return False
    negative = ("没有", "未", "缺少", "无法", "不涉及", "并未", "不含")
    # 按小句判断否定作用域："资料里没有 X，但可能是 Y" 里的 Y 仍然是断言
    clauses = [c.strip() for c in re.split(r"[，。；！？\n]", answer) if c.strip()]
    asserted = [c for c in clauses if not any(mark in c for mark in negative)]
    return not any(fact and fact in clause for fact in key_facts for clause in asserted)
