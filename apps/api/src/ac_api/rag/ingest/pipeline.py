"""入库流水线：load → normalize → chunk → tag → persist。产物是 chunks/*.jsonl。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ac_api.config import chunks_dir, load_config, raw_dir
from ac_api.domain.models import Chunk, content_hash
from ac_api.rag.ingest import manifest as manifest_mod
from ac_api.rag.ingest.chunkers import get_chunker
from ac_api.rag.ingest.loaders.md import load_markdown
from ac_api.rag.ingest.tagger import tag
from ac_api.obs.logger import get_logger

log = get_logger("ingest")


class IngestReport(BaseModel):
    domain: str
    docs_total: int = 0
    docs_added: int = 0
    docs_skipped: int = 0
    docs_replaced: int = 0
    chunks_total: int = 0
    chunks_rejected: int = 0
    rejected_reasons: dict[str, int] = Field(default_factory=dict)

    def add_reject(self, reason: str) -> None:
        self.chunks_rejected += 1
        self.rejected_reasons[reason] = self.rejected_reasons.get(reason, 0) + 1


def chunks_path(domain: str, doc_id: str) -> Path:
    return chunks_dir(domain) / f"{doc_id}.jsonl"


def read_doc_chunks(domain: str, doc_id: str) -> list[Chunk]:
    path = chunks_path(domain, doc_id)
    if not path.exists():
        return []
    return [Chunk.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_chunks(domain: str) -> list[Chunk]:
    out: list[Chunk] = []
    for path in sorted(chunks_dir(domain).glob("*.jsonl")):
        out.extend(
            Chunk.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return out


def ingest_domain(domain: str, *, force: bool = False, source_dir: Path | None = None) -> IngestReport:
    config = load_config()
    spec = config.domain(domain)
    chunker = get_chunker(spec.chunker)
    src = source_dir or raw_dir(domain)
    report = IngestReport(domain=domain)
    manifest = manifest_mod.load_manifest(domain)
    seen_hashes: dict[str, str] = {}

    for path in sorted(src.glob("**/*.md")):
        report.docs_total += 1
        doc = load_markdown(path, domain)
        digest = manifest_mod.file_hash(path)
        prev = manifest.get(doc.doc_id)
        if prev and prev.get("file_hash") == digest and not force and chunks_path(domain, doc.doc_id).exists():
            report.docs_skipped += 1
            for chunk in read_doc_chunks(domain, doc.doc_id):
                seen_hashes.setdefault(chunk.content_hash, chunk.doc_id)
            continue

        drafts = chunker.split(doc, spec)
        chunks: list[Chunk] = []
        for ordinal, draft in enumerate(drafts):
            meta, missing = tag(draft, spec)
            if missing:
                report.add_reject("missing_required_meta:" + ",".join(sorted(missing)))
                continue
            chunk = Chunk(
                chunk_id=f"{domain}:{doc.doc_id}:{ordinal:04d}",
                doc_id=doc.doc_id,
                domain=domain,
                text=draft.text,
                parent_id=draft.parent_heading,
                locator={
                    "doc_title": doc.title,
                    "anchor": draft.heading,
                    "url": doc.source_url,
                    "page": draft.page,
                },
                metadata=meta,
                source_priority=doc.source_priority,
            ).finalize()
            if len(chunk.text) < 40:
                report.add_reject("too_short")
                continue
            owner = seen_hashes.get(chunk.content_hash)
            if owner and owner != doc.doc_id:
                report.add_reject(f"duplicate_of:{owner}")
                continue
            seen_hashes[chunk.content_hash] = doc.doc_id
            report.chunks_total += 1
            chunks.append(chunk)

        tmp = chunks_path(domain, doc.doc_id).with_suffix(".tmp")
        tmp.write_text(
            "\n".join(c.model_dump_json() for c in chunks) + ("\n" if chunks else ""), encoding="utf-8"
        )
        tmp.replace(chunks_path(domain, doc.doc_id))
        report.docs_replaced += 1 if prev else 0
        report.docs_added += 0 if prev else 1
        manifest[doc.doc_id] = {
            "file_hash": digest,
            "chunk_count": len(chunks),
            "ingested_at": manifest_mod.stamp(),
            "path": str(path),
            "title": doc.title,
            "source_priority": doc.source_priority,
        }

    manifest_mod.save_manifest(domain, manifest)
    log.info(
        "ingest_done",
        extra={"domain": domain, "data": {"report": report.model_dump()}},
    )
    return report
