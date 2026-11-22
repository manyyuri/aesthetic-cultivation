import pytest

from ac_api.rag.ingest.loaders.md import load_markdown
from ac_api.rag.ingest.sources.base import LicenseRefused, MissingMeta, SourceError, write_doc
from ac_api.sources import get_source

SPEC = get_source("met")
BODY = """## 作品

Self-Portrait with a Straw Hat，Vincent van Gogh，1887。Oil on canvas。Bequest of Miss Adelaide。

## 著录

馆藏编号 436532，现藏 The Metropolitan Museum of Art。原始记录：https://example.org/1
"""
META = {
    "object_id": "436532",
    "museum": "The Metropolitan Museum of Art",
    "technique": "Oil on canvas",
    "period": "1887",
}


def _write(**over):
    kwargs = dict(
        external_id="436532",
        title="Self-Portrait with a Straw Hat",
        body=BODY,
        meta=dict(META),
        source_url="https://example.org/1",
        dry_run=False,
    )
    kwargs.update(over)
    return write_doc(SPEC, **kwargs)


def test_happy_path_round_trips_through_loader(sandbox):
    doc = _write(external_id="999000")
    assert doc.changed is True
    loaded = load_markdown(__import__("pathlib").Path(doc.path), "art")
    assert loaded.source == "met"
    assert loaded.external_id == "999000"
    assert loaded.license == "CC0-1.0"
    assert loaded.source_url == "https://example.org/1"
    assert loaded.meta["object_id"] == "436532"


def test_license_refused_writes_nothing(sandbox):
    with pytest.raises(LicenseRefused):
        _write(license_id="CC-BY-NC-4.0")


def test_missing_source_url_refused(sandbox):
    with pytest.raises(LicenseRefused):
        _write(source_url="")


def test_missing_required_meta_refused(sandbox):
    meta = dict(META)
    meta.pop("period")
    with pytest.raises(MissingMeta) as exc:
        _write(meta=meta)
    assert exc.value.code == "missing_meta:period"
    assert exc.value.details["missing"] == ["period"]


def test_short_section_refused(sandbox):
    with pytest.raises(SourceError) as exc:
        _write(body="## 作品\n\n太短了。\n")
    assert exc.value.code == "body_too_short"


def test_idempotent_second_write_is_unchanged(sandbox):
    first = _write(external_id="999001")
    second = _write(external_id="999001")
    assert first.changed is True
    assert second.changed is False
