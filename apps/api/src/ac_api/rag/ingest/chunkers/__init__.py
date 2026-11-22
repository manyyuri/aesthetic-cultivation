from __future__ import annotations

from ac_api.rag.ingest.chunkers.act_scene import ActSceneChunker
from ac_api.rag.ingest.chunkers.entry import EntryChunker
from ac_api.rag.ingest.chunkers.work_version import WorkVersionChunker
from ac_api.rag.ingest.chunkers.base import Chunker

CHUNKERS: dict[str, type] = {
    "act_scene": ActSceneChunker,
    "work_version": WorkVersionChunker,
    "entry": EntryChunker,
}


def get_chunker(name: str) -> Chunker:
    if name not in CHUNKERS:
        raise KeyError(f"未知 chunker：{name}（可选：{', '.join(sorted(CHUNKERS))}）")
    return CHUNKERS[name]()  # type: ignore[return-value]
