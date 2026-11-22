"""重排。auto 默认 lexical（离线确定性），显式设 RERANK_PROVIDER=bge 才加载 cross-encoder。"""

from __future__ import annotations

import math
from typing import Protocol

from ac_api.config import load_config, settings
from ac_api.obs.logger import get_logger
from ac_api.rag.index.tokenizer import tokenizer

log = get_logger("rerank")


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class LexicalReranker:
    """词元覆盖率打分，归一到 [0,1]。可解释、可复现、无需模型。"""

    name = "lexical"

    def score(self, query: str, texts: list[str]) -> list[float]:
        # 用词级 token 做分母：字符二元组跨词边界（"舞的""的作"）永远匹配不上，会把覆盖率稀释掉
        q = tokenizer.words(query)
        if not q:
            return [0.0 for _ in texts]
        qset = set(q)
        weights = {t: (1.0 if len(t) > 1 else 0.4) for t in qset}
        total = sum(weights.values()) or 1.0
        out: list[float] = []
        for text in texts:
            tokens = set(tokenizer.words(text)) | set(tokenizer.tokens(text))
            if not tokens:
                out.append(0.0)
                continue
            present = qset & tokens
            covered = sum(weights[t] for t in present) / total
            density = len(present) / max(len(qset), 1)
            bonus = 0.15 if any(len(t) >= 2 and t in text for t in qset) else 0.0
            out.append(min(1.0, 0.7 * covered + 0.15 * density + bonus))
        return out


class BgeReranker:
    name = "bge"

    def __init__(self, model: str, device: str, batch_size: int) -> None:
        from sentence_transformers import CrossEncoder  # 可选依赖

        self._model = CrossEncoder(model, device=device, max_length=512)
        self._batch = batch_size

    def score(self, query: str, texts: list[str]) -> list[float]:
        raw = self._model.predict([(query, t) for t in texts], batch_size=self._batch)
        return [1.0 / (1.0 + math.exp(-float(x))) for x in raw]


def get_reranker() -> Reranker:
    cfg = load_config().providers.get("rerank", {})
    want = (settings().rerank_provider or cfg.get("provider") or "auto").lower()
    if want == "bge":
        bge = cfg.get("bge", {})
        try:
            return BgeReranker(bge.get("model", "BAAI/bge-reranker-v2-m3"), bge.get("device", "cpu"), int(bge.get("batch_size", 8)))
        except Exception as exc:  # pragma: no cover
            log.info("bge_reranker_unavailable", extra={"data": {"error": str(exc)[:200]}})
    return LexicalReranker()
