"""Reciprocal Rank Fusion：等权，不调权重（三领域标注样本不够，调权重是自欺欺人）。"""

from __future__ import annotations


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> tuple[dict[str, float], dict[str, dict[str, int]]]:
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for name, ranking in zip(("bm25", "dense"), rankings, strict=False):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(chunk_id, {})[name] = rank
    return scores, ranks
