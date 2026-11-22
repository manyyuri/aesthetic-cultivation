"""索引构建与版本切换。建新版 → 校验 → 原子写 active.json；检索侧按 mtime 热切换。"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from ac_api.config import index_root, load_config
from ac_api.obs.logger import get_logger
from ac_api.obs.metrics import metrics
from ac_api.rag.index.bm25 import BM25
from ac_api.rag.index.embedding import get_embedder
from ac_api.rag.index.tokenizer import tokenizer
from ac_api.rag.index.vector import LocalVectorStore
from ac_api.rag.ingest.pipeline import load_chunks

log = get_logger("index")


class NoChunks(Exception):
    pass


class IndexManifest(BaseModel):
    domain: str
    index_version: str
    built_at: str
    chunk_count: int
    doc_count: int
    embedding_fingerprint: str
    tokenizer: str
    bm25: dict[str, float]
    git_sha: str | None = None


class ActiveIndex(BaseModel):
    manifest: IndexManifest
    vectors: LocalVectorStore
    bm25: BM25

    model_config = {"arbitrary_types_allowed": True}


def _git_sha() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return None


def version_dir(domain: str, version: str) -> Path:
    return index_root(domain) / version


def active_path(domain: str) -> Path:
    return index_root(domain) / "active.json"


def active_version(domain: str) -> str | None:
    path = active_path(domain)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("index_version")
    except json.JSONDecodeError:
        return None


def next_version(domain: str) -> str:
    today = date.today().isoformat()
    existing = [p.name for p in index_root(domain).iterdir() if p.is_dir()]
    same_day = [int(n.split(".")[1]) for n in existing if n.startswith(today + ".") and n.split(".")[1].isdigit()]
    return f"{today}.{max(same_day, default=0) + 1}"


def _parents(chunks) -> dict[str, str]:
    parents: dict[str, str] = {}
    for chunk in sorted(chunks, key=lambda c: c.chunk_id):
        if chunk.parent_id and chunk.parent_id not in parents:
            parents[chunk.parent_id] = chunk.text
    return parents


def build_index(domain: str) -> IndexManifest:
    config = load_config()
    config.domain(domain)
    chunks = load_chunks(domain)
    if not chunks:
        raise NoChunks(f"{domain} 没有已入库的分块，先跑 make ingest DOMAIN={domain}")

    embedder = get_embedder()
    vectors = embedder.encode([c.text for c in chunks])
    if np.isnan(vectors).any():
        raise ValueError("embedding 含 NaN，拒绝建索引")

    bm25 = BM25()
    bm25.build([(c.chunk_id, c.text) for c in chunks], tokenizer)
    if not bm25.postings:
        raise ValueError("BM25 倒排为空，检查分词器")

    version = next_version(domain)
    target = version_dir(domain, version)
    target.mkdir(parents=True, exist_ok=False)

    store = LocalVectorStore(target / "vectors")
    store.upsert(chunks, vectors, _parents(chunks))
    store.save()
    bm25.save(target / "bm25")

    manifest = IndexManifest(
        domain=domain,
        index_version=version,
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        chunk_count=len(chunks),
        doc_count=len({c.doc_id for c in chunks}),
        embedding_fingerprint=embedder.fingerprint,
        tokenizer=tokenizer.fingerprint(),
        bm25={"k1": bm25.k1, "b": bm25.b},
        git_sha=_git_sha(),
    )
    (target / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    tmp = active_path(domain).with_suffix(".tmp")
    tmp.write_text(json.dumps({"index_version": version}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(active_path(domain))

    metrics.gauge("rag_index_version_info", 1, {"domain": domain, "version": version})
    log.info(
        "index_built",
        extra={"domain": domain, "data": {"version": version, "chunks": len(chunks)}},
    )
    return manifest


_CACHE: dict[str, tuple[float, ActiveIndex]] = {}


def load_active(domain: str) -> ActiveIndex:
    version = active_version(domain)
    if not version:
        raise NoChunks(f"{domain} 还没有可用索引，先跑 make index DOMAIN={domain}")
    path = active_path(domain)
    mtime = path.stat().st_mtime
    cached = _CACHE.get(domain)
    if cached and cached[0] == mtime:
        return cached[1]

    target = version_dir(domain, version)
    manifest = IndexManifest.model_validate_json((target / "manifest.json").read_text(encoding="utf-8"))
    if manifest.embedding_fingerprint != get_embedder().fingerprint:
        raise ValueError(
            f"索引指纹不匹配（{manifest.embedding_fingerprint} ≠ {get_embedder().fingerprint}）："
            "换了 embedding 模型必须重建索引"
        )
    index = ActiveIndex(
        manifest=manifest,
        vectors=LocalVectorStore.load(target / "vectors"),
        bm25=BM25.load(target / "bm25"),
    )
    _CACHE[domain] = (mtime, index)
    metrics.gauge("rag_index_version_info", 1, {"domain": domain, "version": version})
    return index


def rollback(domain: str, version: str) -> None:
    if not version_dir(domain, version).exists():
        raise FileNotFoundError(f"版本不存在：{domain} {version}")
    tmp = active_path(domain).with_suffix(".tmp")
    tmp.write_text(json.dumps({"index_version": version}), encoding="utf-8")
    tmp.replace(active_path(domain))
    log.info("index_rollback", extra={"domain": domain, "data": {"version": version}})
