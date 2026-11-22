"""抓取 → 入库 → 建索引 → 检索：license 全程不丢，且能被召回。"""

from __future__ import annotations

import json
from pathlib import Path

from ac_api.domain.models import RetrieveRequest
from ac_api.rag.index.builder import build_index
from ac_api.rag.ingest.manifest import load_manifest
from ac_api.rag.ingest.pipeline import ingest_domain
from ac_api.rag.ingest.sources.met import MetFetcher
from ac_api.rag.retrieve.pipeline import Retriever
from ac_api.sources import get_source

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sources"


def test_fetch_then_ingest_keeps_license_and_is_retrievable(fake_http, isolated_data):
    http = fake_http(
        {
            "search-painting": {"objectIDs": [436532]},
            "object-436532": json.loads((FIXTURES / "met_object_436532.json").read_text(encoding="utf-8")),
        }
    )
    report = MetFetcher(get_source("met"), http).fetch(limit=1)
    assert report.written == 1, report.refused

    ingest = ingest_domain("art", force=True)
    assert ingest.chunks_rejected == 0, ingest.rejected_reasons

    manifest = load_manifest("art")
    assert manifest["met_436532"]["license"] == "CC0-1.0"
    assert manifest["met_436532"]["source"] == "met"
    assert manifest["met_436532"]["source_url"].startswith("https://www.metmuseum.org/")

    build_index("art")
    response = Retriever().retrieve(
        RetrieveRequest(domain="art", query="Self-Portrait with a Straw Hat Vincent van Gogh", top_k=3)
    )
    assert response.evidence_status == "found"
    assert any(chunk.doc_id == "met_436532" for chunk in response.chunks)
    assert all(chunk.source.startswith("《") for chunk in response.chunks)
    assert all(chunk.metadata.get("museum") for chunk in response.chunks)


def test_dry_run_writes_nothing(fake_http, isolated_data):
    raw_dir = Path(isolated_data) / "raw" / "art"
    before = {p.name for p in raw_dir.glob("met_*.md")}
    http = fake_http(
        {
            "search-painting": {"objectIDs": [436532]},
            "object-436532": json.loads((FIXTURES / "met_object_436532.json").read_text(encoding="utf-8")),
        }
    )
    report = MetFetcher(get_source("met"), http).fetch(limit=1, dry_run=True)
    after = {p.name for p in raw_dir.glob("met_*.md")}
    assert report.dry_run is True
    assert report.preview and "license" in report.preview[0]["head"]
    assert before == after
