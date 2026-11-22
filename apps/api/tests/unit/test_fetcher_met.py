import json
from pathlib import Path

from ac_api.rag.ingest.sources.met import MetFetcher
from ac_api.sources import get_source

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sources"
SPEC = get_source("met")


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_public_domain_only_and_front_matter(fake_http, isolated_data):
    http = fake_http(
        {
            "search-painting": {"objectIDs": [436532, 490190]},
            "object-436532": _load("met_object_436532.json"),
            "object-490190": _load("met_object_nonpd.json"),
        }
    )
    report = MetFetcher(SPEC, http).fetch(limit=5)
    assert report.written == 1
    assert report.refused[0].reason == "not_public_domain"

    written = Path(isolated_data) / "raw" / "art" / "met_436532.md"
    text = written.read_text(encoding="utf-8")
    assert 'license: "CC0-1.0"' in text
    assert 'source: "met"' in text
    assert "https://www.metmuseum.org/art/collection/search/436532" in text
    assert '"image_url"' in text
    assert text.count("## ") == 3


def test_second_fetch_is_skipped_not_rewritten(fake_http, isolated_data):
    http = fake_http(
        {"search-painting": {"objectIDs": [436532]}, "object-436532": _load("met_object_436532.json")}
    )
    MetFetcher(SPEC, http).fetch(limit=1)
    second = MetFetcher(SPEC, http).fetch(limit=1)
    assert second.written == 0
    assert second.skipped == 1


def test_missing_period_is_refused(fake_http, isolated_data):
    data = _load("met_object_436532.json")
    data.update({"period": "", "objectDate": ""})
    http = fake_http({"search-painting": {"objectIDs": [1]}, "object-1": data})
    report = MetFetcher(SPEC, http).fetch(limit=1)
    assert report.written == 0
    assert report.refused[0].reason == "missing_meta:period"
    assert report.missing_meta == {"period": 1}
