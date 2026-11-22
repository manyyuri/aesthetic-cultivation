from __future__ import annotations

from fastapi import APIRouter

from ac_api import __version__
from ac_api.config import load_config
from ac_api.obs.metrics import metrics
from ac_api.rag.index.builder import active_version, index_root

router = APIRouter(tags=["health"])


def _index_state(domain: str) -> dict:
    version = active_version(domain)
    if not version:
        return {"domain": domain, "version": None, "chunk_count": 0, "ready": False}
    manifest = index_root(domain) / version / "manifest.json"
    chunk_count = 0
    if manifest.exists():
        import json

        chunk_count = json.loads(manifest.read_text(encoding="utf-8")).get("chunk_count", 0)
    return {"domain": domain, "version": version, "chunk_count": chunk_count, "ready": True}


@router.get("/api/healthz")
def healthz() -> dict:
    config = load_config()
    indexes = {d: _index_state(d) for d in config.domains}
    ready = any(i["ready"] for i in indexes.values())
    return {
        "ok": True,
        "version": __version__,
        "index_ready": ready,
        "indexes": indexes,
        "domains": [
            {"domain": d.domain, "display_name": d.display_name} for d in config.domains.values()
        ],
        "hint": None if ready else "索引还没建：make seed && make ingest DOMAIN=ballet && make index DOMAIN=ballet",
    }


@router.get("/api/stats")
def stats() -> dict:
    config = load_config()
    return {
        "indexes": {d: _index_state(d) for d in config.domains},
        "metrics": metrics.snapshot(),
        "retrieval_latency": metrics.histogram_stats("rag_retrieve_latency_seconds"),
        "run_latency": metrics.histogram_stats("run_duration_seconds"),
    }
