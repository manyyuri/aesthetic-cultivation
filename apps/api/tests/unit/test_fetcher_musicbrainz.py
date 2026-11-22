import json
from pathlib import Path

from ac_api.rag.ingest.loaders.md import load_markdown
from ac_api.rag.ingest.sources.musicbrainz import MusicBrainzFetcher
from ac_api.sources import get_source

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sources"
SPEC = get_source("musicbrainz")


def _release() -> dict:
    return json.loads((FIXTURES / "mb_release.json").read_text(encoding="utf-8"))


def _fetch(fake_http, release: dict, data_root):
    mbid = release["id"]
    http = fake_http({"search-symphony": {"releases": [{"id": mbid}]}, f"release-{mbid}": release})
    return MusicBrainzFetcher(SPEC, http).fetch(limit=1), mbid


def test_tracks_become_movements_with_exact_timings(fake_http, isolated_data):
    report, mbid = _fetch(fake_http, _release(), isolated_data)
    assert report.written == 1
    doc = load_markdown(Path(isolated_data) / "raw" / "music" / f"musicbrainz_{mbid}.md", "music")
    assert doc.meta["duration_s"] > 0
    movement_sections = [s for s in doc.sections if s.heading and s.heading.startswith("第")]
    assert len(movement_sections) == 4
    first = movement_sections[0]
    assert first.meta["movement"] == 1
    assert first.meta["movement_from_s"] == 0
    second = movement_sections[1]
    assert second.meta["movement_from_s"] == first.meta["movement_duration_s"]


def test_missing_track_length_refused(fake_http, isolated_data):
    release = _release()
    release["media"][0]["tracks"][2]["length"] = None
    report, _ = _fetch(fake_http, release, isolated_data)
    assert report.written == 0
    assert report.refused[0].reason == "missing_track_length"


def test_too_many_tracks_refused(fake_http, isolated_data):
    release = _release()
    tracks = release["media"][0]["tracks"]
    release["media"][0]["tracks"] = [dict(tracks[0], position=i) for i in range(1, SPEC.max_tracks + 2)]
    report, _ = _fetch(fake_http, release, isolated_data)
    assert report.refused[0].reason == "too_many_tracks"
