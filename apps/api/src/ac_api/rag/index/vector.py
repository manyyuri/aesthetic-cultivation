"""向量存储。默认 LocalVectorStore（npy + jsonl，精确余弦），Chroma 只留槽位。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ac_api.domain.models import Chunk


class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: np.ndarray, parents: dict[str, str]) -> None: ...
    def query(
        self, vector: np.ndarray, top_n: int, where: dict[str, Any] | None = None
    ) -> list[tuple[str, float]]: ...


def _match(meta: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    for key, cond in where.items():
        value = meta.get(key)
        if isinstance(cond, dict):
            if "$eq" in cond and value != cond["$eq"]:
                return False
            if "$in" in cond and value not in cond["$in"]:
                return False
        elif value != cond:
            return False
    return True


class LocalVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.ids: list[str] = []
        self.payload: dict[str, dict[str, Any]] = {}
        self._matrix: np.ndarray | None = None

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray, parents: dict[str, str]) -> None:
        self.ids = [c.chunk_id for c in chunks]
        self._matrix = np.asarray(vectors, dtype=np.float32)
        self.payload = {
            c.chunk_id: {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "domain": c.domain,
                "text": c.text,
                "locator": c.locator.model_dump(),
                "metadata": c.metadata,
                "source_priority": c.source_priority,
                "parent_id": c.parent_id,
                "parent_excerpt": parents.get(c.parent_id or "", "")[:300] or None,
                "content_hash": c.content_hash,
            }
            for c in chunks
        }

    def save(self) -> None:
        assert self._matrix is not None
        np.save(self.path / "vectors.npy", self._matrix)
        (self.path / "ids.json").write_text(json.dumps(self.ids), encoding="utf-8")
        lines = [json.dumps(p, ensure_ascii=False) for p in self.payload.values()]
        (self.path / "payload.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> LocalVectorStore:
        store = cls(path)
        store._matrix = np.load(path / "vectors.npy")
        store.ids = json.loads((path / "ids.json").read_text(encoding="utf-8"))
        store.payload = {}
        for line in (path / "payload.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                store.payload[item["chunk_id"]] = item
        return store

    def query(
        self, vector: np.ndarray, top_n: int, where: dict[str, Any] | None = None
    ) -> list[tuple[str, float]]:
        if self._matrix is None or not len(self.ids):
            return []
        vec = np.asarray(vector, dtype=np.float32).reshape(-1)
        scores = self._matrix @ vec
        order = np.argsort(-scores)
        out: list[tuple[str, float]] = []
        for idx in order:
            chunk_id = self.ids[int(idx)]
            payload = self.payload.get(chunk_id, {})
            if not _match({**payload.get("metadata", {}), "domain": payload.get("domain")}, where):
                continue
            out.append((chunk_id, float(scores[int(idx)])))
            if len(out) >= top_n:
                break
        return out


class ChromaVectorStore:  # pragma: no cover - 见 docs/DECISIONS.md#chroma
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Chroma 实现留槽位：当前使用 LocalVectorStore（见 DECISIONS）")
