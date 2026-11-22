"""向量化。auto 默认走确定性 hashed 兜底（离线可跑），显式设 EMBED_PROVIDER=bge 才加载 bge-m3。"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from ac_api.config import load_config, settings
from ac_api.obs.logger import get_logger
from ac_api.rag.index.tokenizer import tokenizer

log = get_logger("embedding")


class Embedder(Protocol):
    name: str
    dim: int
    fingerprint: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class HashedEmbedder:
    """确定性 bag-of-tokens 哈希向量。可离线、可复现；不是语义模型，仅作兜底。"""

    name = "hashed"

    def __init__(self, dim: int = 1024, tag: str = "v1") -> None:
        self.dim = dim
        self.tag = tag

    @property
    def fingerprint(self) -> str:
        return f"hashed:{self.dim}:{self.tag}:{tokenizer.fingerprint()}"

    def _hash(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dim

    def encode(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenizer.tokens(text):
                matrix[row, self._hash(token)] += 1.0
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


class BgeEmbedder:
    name = "bge"

    def __init__(self, model: str, device: str, batch_size: int, max_length: int) -> None:
        from sentence_transformers import SentenceTransformer  # 可选依赖

        self._model = SentenceTransformer(model, device=device)
        self._model.max_seq_length = max_length
        self._batch = batch_size
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self._tag = model

    @property
    def fingerprint(self) -> str:
        return f"bge:{self._tag}:{self.dim}"

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(
            texts, batch_size=self._batch, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vectors, dtype=np.float32)


def resolve_provider() -> str:
    cfg = load_config().providers.get("embedding", {})
    want = (settings().embed_provider or cfg.get("provider") or "auto").lower()
    if want in ("bge", "local"):
        return "bge"
    if want == "hashed":
        return "hashed"
    return "hashed"  # auto：确定性兜底，避免首次运行时静默下载 2GB 模型


def get_embedder() -> Embedder:
    cfg = load_config().providers.get("embedding", {})
    if resolve_provider() == "bge":
        bge = cfg.get("bge", {})
        try:
            return BgeEmbedder(
                bge.get("model", "BAAI/bge-m3"),
                bge.get("device", "cpu"),
                int(bge.get("batch_size", 16)),
                int(bge.get("max_length", 512)),
            )
        except Exception as exc:  # pragma: no cover - 依赖缺失时兜底
            log.info("bge_unavailable", extra={"data": {"error": str(exc)[:200]}})
    return HashedEmbedder(
        dim=int(cfg.get("hashed_dim", 1024)), tag=str(cfg.get("hashed_model_tag", "v1"))
    )
