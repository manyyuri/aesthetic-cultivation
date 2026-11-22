"""评审闸门：evidence / anchor / tone / novelty。任一不过 ⇒ REPLACE 或 REWRITE。"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ac_api.config import DomainSpec, load_config
from ac_api.curation.anchors import validate_anchor
from ac_api.curation.candidates import Candidate
from ac_api.curation.write import WrittenItem
from ac_api.domain.models import Chunk
from ac_api.rag.index.tokenizer import tokenizer

SENT_SPLIT = re.compile(r"[。！？!?；;]")
NUMBER_RE = re.compile(r"\d{3,4}")


class ReviewIssue(BaseModel):
    gate: Literal["evidence", "anchor", "tone", "novelty"]
    problem: str
    fix_hint: str


class ReviewVerdict(BaseModel):
    verdict: Literal["PASS", "REWRITE", "REPLACE", "FAIL"]
    issues: list[ReviewIssue] = Field(default_factory=list)
    loop: int = 1


def _rules() -> dict:
    return load_config().curation.get("rules", {})


def review(
    written: WrittenItem,
    candidate: Candidate,
    evidence: list[Chunk],
    spec: DomainSpec,
    *,
    hook_max_chars: int = 60,
    loop: int = 1,
) -> ReviewVerdict:
    issues: list[ReviewIssue] = []

    # 1) evidence：hook 的每个数字与主要词元必须能在原文里找到
    corpus = "\n".join(c.text for c in evidence)
    corpus_tokens = set(tokenizer.tokens(corpus))
    hook_tokens = [t for t in tokenizer.tokens(written.hook) if len(t) >= 2]
    if hook_tokens:
        missing = [t for t in hook_tokens if t not in corpus_tokens]
        coverage = 1 - len(missing) / len(hook_tokens)
        if coverage < 0.6:
            issues.append(
                ReviewIssue(
                    gate="evidence",
                    problem=f"hook 与原文重合度 {coverage:.0%}",
                    fix_hint="换一条更贴原文的句子",
                )
            )
    for number in NUMBER_RE.findall(written.hook):
        if number not in corpus:
            issues.append(
                ReviewIssue(gate="evidence", problem=f"数字 {number} 不在原文里", fix_hint="删除或换原文数字")
            )

    # 2) anchor
    ok, why = validate_anchor(candidate.domain, written.anchor, candidate.metadata)
    if not ok:
        issues.append(ReviewIssue(gate="anchor", problem=why, fix_hint="换候选或修元数据"))

    # 3) tone
    banned = list(_rules().get("marketing_words", [])) + list(_rules().get("hedge_words", []))
    hit = [w for w in banned if w in written.hook]
    if hit:
        issues.append(
            ReviewIssue(gate="tone", problem=f"出现禁用词：{'、'.join(hit)}", fix_hint="重写 hook")
        )
    if len(written.hook) > hook_max_chars:
        issues.append(
            ReviewIssue(
                gate="tone", problem=f"hook {len(written.hook)} 字 > {hook_max_chars}", fix_hint="压缩到一句"
            )
        )
    sentences = [s for s in SENT_SPLIT.split(written.hook) if s.strip()]
    if len(sentences) > int(_rules().get("hook_max_sentences", 2)):
        issues.append(ReviewIssue(gate="tone", problem="hook 超过 2 句", fix_hint="只留一句"))

    # 4) novelty（由 compose 传入的 reasons 表达）
    if candidate.reasons:
        issues.append(
            ReviewIssue(gate="novelty", problem="；".join(candidate.reasons), fix_hint="换候选")
        )

    if not issues:
        return ReviewVerdict(verdict="PASS", loop=loop)
    if any(i.gate in ("anchor", "novelty", "evidence") for i in issues):
        return ReviewVerdict(verdict="REPLACE", issues=issues, loop=loop)
    return ReviewVerdict(verdict="REWRITE", issues=issues, loop=loop)
