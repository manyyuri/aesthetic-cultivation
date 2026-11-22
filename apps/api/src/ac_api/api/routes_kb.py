from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ac_api.api.deps import require_admin
from ac_api.api.jobs import get as get_job
from ac_api.api.jobs import submit
from ac_api.api.schemas import FetchRequest, IngestRequest, IndexRequest, RollbackRequest
from ac_api.config import load_config
from ac_api.domain.models import RetrieveRequest, RetrieveResponse
from ac_api.rag.index.builder import active_version, index_root, rollback
from ac_api.rag.index.builder import build_index
from ac_api.rag.ingest.pipeline import ingest_domain, load_chunks, read_doc_chunks
from ac_api.rag.ingest.manifest import load_manifest
from ac_api.rag.retrieve.pipeline import Retriever

router = APIRouter(prefix="/api", tags=["kb"])


@router.get("/sources")
def list_sources() -> list[dict]:
    from ac_api.sources import as_public, sources

    return [as_public(spec) for spec in sources().sources.values()]


@router.post("/kb/fetch", dependencies=[Depends(require_admin)])
async def fetch(body: FetchRequest) -> dict:
    from ac_api.rag.ingest.sources import get_fetcher

    job_id = submit(
        "fetch",
        lambda: get_fetcher(body.source)
        .fetch(limit=body.limit, query=body.query, dry_run=body.dry_run)
        .model_dump(),
    )
    return {"job_id": job_id}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(body: RetrieveRequest) -> RetrieveResponse:
    return Retriever().retrieve(body)


@router.post("/kb/ingest", dependencies=[Depends(require_admin)])
async def ingest(body: IngestRequest) -> dict:
    job_id = submit("ingest", ingest_domain, body.domain, force=body.force)
    return {"job_id": job_id}


@router.post("/kb/index", dependencies=[Depends(require_admin)])
async def index(body: IndexRequest) -> dict:
    job_id = submit("index", build_index, body.domain)
    return {"job_id": job_id}


@router.post("/kb/rollback", dependencies=[Depends(require_admin)])
def rollback_endpoint(body: RollbackRequest) -> dict:
    rollback(body.domain, body.index_version)
    return {"domain": body.domain, "active": body.index_version}


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="没有这个 job")
    return record.model_dump()


@router.get("/kb/docs")
def docs(domain: str = Query(...)) -> dict:
    load_config().domain(domain)
    manifest = load_manifest(domain)
    chunks = load_chunks(domain)
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.doc_id] = counts.get(chunk.doc_id, 0) + 1
    rows = [
        {
            "doc_id": doc_id,
            "title": info.get("title", doc_id),
            "source_priority": info.get("source_priority", "secondary_web"),
            "chunk_count": counts.get(doc_id, info.get("chunk_count", 0)),
            "ingested_at": info.get("ingested_at"),
            "source": info.get("source", "manual"),
            "license": info.get("license"),
            "retrieved_at": info.get("retrieved_at"),
            "source_url": info.get("source_url"),
        }
        for doc_id, info in sorted(manifest.items())
    ]
    return {"domain": domain, "index_version": active_version(domain), "docs": rows}


@router.get("/kb/docs/{doc_id}/chunks")
def doc_chunks(doc_id: str, domain: str = Query(...)) -> list[dict]:
    license_id = (load_manifest(domain).get(doc_id) or {}).get("license")
    return [
        {
            "chunk_id": c.chunk_id,
            "anchor": c.locator.anchor,
            "metadata": c.metadata,
            "tokens": c.tokens,
            "content_hash": c.content_hash,
            "license": license_id,
            "text": c.text,
        }
        for c in read_doc_chunks(domain, doc_id)
    ]


@router.get("/kb/versions")
def versions(domain: str = Query(...)) -> dict:
    root = index_root(domain)
    return {
        "domain": domain,
        "active": active_version(domain),
        "versions": sorted(p.name for p in root.iterdir() if p.is_dir()),
    }
