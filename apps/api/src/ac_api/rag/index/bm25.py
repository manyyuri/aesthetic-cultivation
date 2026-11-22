"""BM25（自实现，零依赖）：倒排 + df/avgdl 持久化到 JSON，便于审计与回滚。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

from ac_api.rag.index.tokenizer import Tokenizer, tokenizer as default_tokenizer


class BM25:
    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.postings: dict[str, dict[str, int]] = {}
        self.lens: dict[str, int] = {}
        self.avgdl = 0.0

    def build(self, docs: Iterable[tuple[str, str]], tokenizer: Tokenizer | None = None) -> None:
        tok = tokenizer or default_tokenizer
        self.postings, self.lens = {}, {}
        for chunk_id, text in docs:
            tokens = tok.tokens(text)
            self.lens[chunk_id] = len(tokens)
            for token in tokens:
                bucket = self.postings.setdefault(token, {})
                bucket[chunk_id] = bucket.get(chunk_id, 0) + 1
        self.avgdl = (sum(self.lens.values()) / len(self.lens)) if self.lens else 0.0

    def search(self, tokens: list[str], top_k: int = 50) -> list[tuple[str, float]]:
        if not self.lens or not self.avgdl:
            return []
        n = len(self.lens)
        scores: dict[str, float] = {}
        for token in set(tokens):
            bucket = self.postings.get(token)
            if not bucket:
                continue
            df = len(bucket)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for chunk_id, tf in bucket.items():
                dl = self.lens.get(chunk_id, 0)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + idf * tf * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:top_k]
        return ranked

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "k1": self.k1,
            "b": self.b,
            "avgdl": self.avgdl,
            "lens": self.lens,
            "postings": {t: b for t, b in self.postings.items() if b},
        }
        (path / "bm25.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> BM25:
        payload = json.loads((path / "bm25.json").read_text(encoding="utf-8"))
        index = cls(float(payload["k1"]), float(payload["b"]))
        index.avgdl = float(payload["avgdl"])
        index.lens = {k: int(v) for k, v in payload["lens"].items()}
        index.postings = {t: {c: int(n) for c, n in b.items()} for t, b in payload["postings"].items()}
        return index
