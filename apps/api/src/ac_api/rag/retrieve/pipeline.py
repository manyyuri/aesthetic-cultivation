"""检索流水线：双路召回 → RRF → 重排 → 阈值 → 父级扩展 → 去重配额 → 预算裁剪。"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from ac_api.config import Config, load_config
from ac_api.domain.models import (
    Chunk,
    RetrieveRequest,
    RetrieveResponse,
    RetrievedChunk,
)
from ac_api.obs.logger import get_logger
from ac_api.obs.metrics import metrics
from ac_api.rag.index.builder import ActiveIndex, load_active
from ac_api.rag.index.embedding import Embedder, get_embedder
from ac_api.rag.index.tokenizer import tokenizer
from ac_api.rag.retrieve.cache import RetrieveCache
from ac_api.rag.retrieve.filters import relaxations, validate_filter
from ac_api.rag.retrieve.rerank import Reranker, get_reranker
from ac_api.rag.retrieve.rrf import rrf_fuse

log = get_logger("retrieve")


class RetrieveError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class Retriever:
    def __init__(
        self,
        config: Config | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        cache: RetrieveCache | None = None,
    ) -> None:
        self.config = config or load_config()
        self.embedder = embedder or get_embedder()
        self.reranker = reranker or get_reranker()
        cfg = self.config.cache
        self.cache = cache or RetrieveCache(cfg.max_entries, cfg.ttl_s, cfg.task_scope_ttl_s)

    # ---- public ----
    def retrieve(self, req: RetrieveRequest) -> RetrieveResponse:
        started = time.monotonic()
        spec = self.config.domain(req.domain)  # UnknownDomain 由上层映射成 400
        query = (req.query or "").strip()
        if not query:
            raise RetrieveError("empty_query", "query 不能为空")
        if len(query) > 500:
            raise RetrieveError("query_too_long", "query 超过 500 字", {"len": len(query)})

        top_k = max(1, min(req.top_k or self.config.retrieval.top_k_default, self.config.retrieval.top_k_max))
        where = validate_filter(spec, req.meta_filter)
        index = load_active(req.domain)  # NoChunks → 上层映射 503

        key = self._cache_key(req.domain, query, top_k, where, index.manifest.index_version)
        if self.config.cache.enabled:
            hit = self.cache.get(key, req.task_id)
            if hit:
                payload, scope = hit
                cached = payload.model_copy(deep=True)
                cached.request_id = f"r_{uuid.uuid4().hex[:12]}"
                cached.cache_hit = True
                cached.cache_scope = scope
                cached.latency_ms = int((time.monotonic() - started) * 1000)
                metrics.inc("rag_cache_hit_total", {"scope": scope})
                metrics.inc(
                    "rag_retrieve_total",
                    {"domain": req.domain, "evidence_status": cached.evidence_status},
                )
                return cached

        pool = int(spec.retrieval.get("recall_pool", self.config.retrieval.recall_pool))
        t_bm25 = time.monotonic()
        bm25_rank = [cid for cid, _ in index.bm25.search(tokenizer.tokens(query), pool)]
        bm25_ms = (time.monotonic() - t_bm25) * 1000

        warnings: list[str] = []
        t_dense = time.monotonic()
        dense_hits: list[tuple[str, float]] = []
        try:
            vector = self.embedder.encode([query])[0]
            dense_hits = index.vectors.query(vector, pool, where)
        except Exception as exc:  # 单路失败只降级
            warnings.append("dense_unavailable")
            log.info("dense_failed", extra={"data": {"error": str(exc)[:200]}})
        dense_ms = (time.monotonic() - t_dense) * 1000
        if not bm25_rank and not dense_hits:
            metrics.inc("rag_insufficient_total", {"domain": req.domain})
            return self._insufficient(req, index, warnings, started)

        fused, ranks = rrf_fuse([bm25_rank, [cid for cid, _ in dense_hits]], self.config.retrieval.rrf_k)

        # 元数据过滤（BM25 路没有 where）
        candidates: list[tuple[str, float, dict]] = []
        for chunk_id, score in sorted(fused.items(), key=lambda kv: -kv[1]):
            payload = index.vectors.payload.get(chunk_id)
            if not payload:
                continue
            if where and not _match_payload(payload, where):
                continue
            # 与 chunker 的最小长度保持一致（40 字）；再严格就会把"第三幕只有两句话"这类合法短节滤掉
            if len(payload.get("text", "")) < 40:
                continue
            candidates.append((chunk_id, score, payload))
        after_filter = len(candidates)

        pool_n = self.config.retrieval.rerank_pool
        candidates = candidates[:pool_n]
        texts = [c[2]["text"] for c in candidates]
        scores = self.reranker.score(query, texts) if texts else []
        ranked = sorted(zip(candidates, scores, strict=False), key=lambda pair: -pair[1])

        min_score = (
            float(req.options["min_score"])
            if req.options.get("min_score")
            else self.config.min_score_for(self.reranker.name)
        )
        kept = [(c, s) for c, s in ranked if s >= min_score]
        if not kept:
            status_weak = [(c, s) for c, s in ranked if s >= min_score * 0.7 and s > 0]
            if status_weak:
                kept = status_weak[:top_k]
                evidence_status = "weak"
            else:
                metrics.inc("rag_insufficient_total", {"domain": req.domain})
                return self._insufficient(req, index, warnings, started)
        else:
            evidence_status = "found"

        # 去重 + 每文档配额 + top_k
        picked: list[tuple[str, float, dict]] = []
        seen_hash: set[str] = set()
        per_doc: dict[str, int] = {}
        for (chunk_id, _rrf, payload), score in kept:
            h = payload.get("content_hash") or chunk_id
            if h in seen_hash:
                continue
            doc_id = payload["doc_id"]
            if per_doc.get(doc_id, 0) >= self.config.retrieval.max_chunks_per_doc:
                continue
            seen_hash.add(h)
            per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
            picked.append((chunk_id, score, payload))
            if len(picked) >= top_k:
                break

        chunks: list[RetrievedChunk] = []
        used_tokens = 0
        for i, (chunk_id, score, payload) in enumerate(picked, start=1):
            from ac_api.domain.models import estimate_tokens

            cost = estimate_tokens(payload["text"])
            if used_tokens + cost > self.config.retrieval.budget_tokens:
                warnings.append("truncated_for_budget")
                break
            used_tokens += cost
            chunks.append(
                RetrievedChunk(
                    citation_id=f"S{i}",
                    chunk_id=chunk_id,
                    content=payload["text"],
                    context_prefix=payload.get("parent_excerpt") if self.config.retrieval.expand_parent else None,
                    source=_render_source(spec, payload),
                    locator=payload["locator"],
                    doc_id=payload["doc_id"],
                    domain=payload["domain"],
                    metadata=payload.get("metadata", {}),
                    scores={
                        "bm25_rank": float(ranks.get(chunk_id, {}).get("bm25", 0)),
                        "dense_rank": float(ranks.get(chunk_id, {}).get("dense", 0)),
                        "rrf": round(float(_rrf_of(picked, chunk_id, 0.0)), 6),
                        "rrf_raw": round(float(fused.get(chunk_id, 0.0)), 6),
                        "rerank": round(float(score), 4),
                    },
                    source_priority=payload.get("source_priority", "secondary_web"),
                )
            )

        response = RetrieveResponse(
            request_id=f"r_{uuid.uuid4().hex[:12]}",
            domain=req.domain,
            index_version=index.manifest.index_version,
            evidence_status=evidence_status,  # type: ignore[arg-type]
            latency_ms=int((time.monotonic() - started) * 1000),
            chunks=chunks,
            stats={
                "recall_pool_bm25": len(bm25_rank),
                "recall_pool_dense": len(dense_hits),
                "after_filter": after_filter,
                "after_rerank": len(kept),
            },
            warnings=warnings,
        )
        if self.config.cache.enabled:
            self.cache.set(key, response, req.task_id)
        metrics.inc("rag_retrieve_total", {"domain": req.domain, "evidence_status": evidence_status})
        metrics.observe("rag_retrieve_latency_seconds", bm25_ms / 1000, {"domain": req.domain, "stage": "bm25"})
        metrics.observe("rag_retrieve_latency_seconds", dense_ms / 1000, {"domain": req.domain, "stage": "dense"})
        metrics.observe(
            "rag_retrieve_latency_seconds", response.latency_ms / 1000, {"domain": req.domain, "stage": "total"}
        )
        log.info(
            "retrieve_done",
            extra={
                "domain": req.domain,
                "data": {
                    "status": evidence_status,
                    "chunks": len(chunks),
                    "latency_ms": response.latency_ms,
                    "index_version": index.manifest.index_version,
                },
            },
        )
        return response

    # ---- helpers ----
    def _insufficient(
        self, req: RetrieveRequest, index: ActiveIndex, warnings: list[str], started: float
    ) -> RetrieveResponse:
        spec = self.config.domain(req.domain)
        return RetrieveResponse(
            request_id=f"r_{uuid.uuid4().hex[:12]}",
            domain=req.domain,
            index_version=index.manifest.index_version,
            evidence_status="insufficient",
            latency_ms=int((time.monotonic() - started) * 1000),
            chunks=[],
            warnings=warnings,
            missing_hint=f"知识库暂无覆盖该问题的档案（{spec.display_name}）",
            suggested_queries=relaxations(spec, req.meta_filter),
        )

    def _cache_key(
        self, domain: str, query: str, top_k: int, where: dict | None, version: str
    ) -> str:
        raw = json.dumps(
            [domain, query.lower(), top_k, where, version], ensure_ascii=False, sort_keys=True
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _match_payload(payload: dict, where: dict[str, Any]) -> bool:
    meta = payload.get("metadata", {})
    for key, cond in where.items():
        value = meta.get(key)
        if isinstance(cond, dict):
            if "$eq" in cond and value != cond["$eq"]:
                return False
        elif value != cond:
            return False
    return True


def _rrf_of(picked: list, chunk_id: str, default: float) -> float:
    for cid, score, _payload in picked:
        if cid == chunk_id:
            return float(score)
    return default


def _render_source(spec, payload: dict) -> str:
    locator = payload["locator"]
    anchor = locator.get("anchor") or ""
    page = locator.get("page")
    suffix = anchor + (f" p.{page}" if page else "")
    title = str(locator.get("doc_title", "")).replace("《", "").replace("》", "")
    try:
        return spec.citation_style.format(doc_title=title, locator=suffix)
    except (KeyError, IndexError):
        return f"《{locator.get('doc_title', '')}》{suffix}"


_RETRIEVER: Retriever | None = None


def get_retriever() -> Retriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = Retriever()
    return _RETRIEVER
