from __future__ import annotations

from fastapi.testclient import TestClient

from ac_api.app import app


def test_sources_endpoint_exposes_license():
    with TestClient(app) as client:
        rows = client.get("/api/sources").json()
    assert {row["name"] for row in rows} >= {"met", "musicbrainz", "internet_archive"}
    for row in rows:
        assert row["license"]
        assert row["domain"] in ("art", "music", "ballet")


def test_kb_docs_exposes_source_and_license():
    from ac_api.rag.ingest.pipeline import ingest_domain

    ingest_domain("art")
    with TestClient(app) as client:
        payload = client.get("/api/kb/docs", params={"domain": "art"}).json()
    assert payload["docs"]
    row = next(doc for doc in payload["docs"] if doc["doc_id"] == "art_monet_impression_sunrise_1872")
    assert row["source"] == "manual"
    assert row["license"] == "CC-BY-SA-4.0"
    assert row["source_url"].startswith("https://")


def test_ingest_document_without_license_is_rejected(tmp_path, sandbox):
    from ac_api.rag.ingest.pipeline import ingest_domain

    raw = tmp_path / "nolike"
    raw.mkdir()
    (raw / "no_license.md").write_text(
        "---\ndoc_id: no_license\ndomain: art\ntitle: 无许可\n"
        'meta: {"object_id":"x","museum":"m","technique":"t","period":"p"}\n---\n\n'
        "## 作品\n\n" + "这是一段足够长的正文，用来避免触发过短检查，但没有 license 字段。" * 2 + "\n",
        encoding="utf-8",
    )
    report = ingest_domain("art", source_dir=raw)
    assert report.docs_rejected == 1
    assert report.rejected_reasons["missing_license"] == 1
