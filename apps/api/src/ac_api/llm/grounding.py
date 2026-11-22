"""作答前的硬闸门 + 作答后的引用校验。

只做语言无关、高精度的判断（数字/年份/空证据），
跨语言的实体匹配交给模型——用词面向量做跨语言门禁只会误杀。
"""

from __future__ import annotations

import re
from typing import Sequence

YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
CITE_RE = re.compile(r"\[(S\d+)\]")
FACT_HINT_RE = re.compile(r"\d|《|》|“|”|\"")
META_MARKERS = ("资料里没有", "资料中没有", "没有能支撑", "无法确认", "查不到", "资料不足", "未提供")


def precheck(question: str, evidence_texts: Sequence[str]) -> str | None:
    """返回拒答理由；None 表示可以作答。"""
    if not evidence_texts:
        return "no_evidence"
    corpus = "\n".join(evidence_texts)
    for year in YEAR_RE.findall(question):
        if year not in corpus:
            return f"year_not_in_evidence:{year}"
    return None


def _is_meta(sentence: str) -> bool:
    return any(marker in sentence for marker in META_MARKERS)


def uncited_fact_sentences(answer: str, valid_ids: set[str]) -> list[str]:
    """找出"带具体事实但没有有效引用"的句子。meta 说明句（如'资料里没有…'）不算。"""
    bad: list[str] = []
    for sentence in re.split(r"(?<=[。！？\n])", answer):
        text = sentence.strip()
        if not text or _is_meta(text) or not FACT_HINT_RE.search(text):
            continue
        cites = CITE_RE.findall(text)
        if not cites or any(cite not in valid_ids for cite in cites):
            bad.append(text[:120])
    return bad


def has_any_citation(answer: str, valid_ids: set[str]) -> bool:
    return any(cite in valid_ids for cite in CITE_RE.findall(answer))
