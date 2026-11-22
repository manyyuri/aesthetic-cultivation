from pathlib import Path

import pytest

from ac_api.rag.ingest.loaders.md import load_markdown
from ac_api.rag.ingest.sources.base import SourceError
from ac_api.rag.ingest.sources.ia import IaFetcher
from ac_api.sources import IaIdentifier, get_source

BASE = get_source("internet_archive")
PARA = "舞蹈在十九世纪被写成一套可教授的身体技术，教师用把杆与镜面把动作固定下来，学生按拍子重复。" * 3


def _spec(*identifiers: IaIdentifier):
    return BASE.model_copy(update={"identifiers": list(identifiers)})


def _http(fake_http, metadata: dict):
    return fake_http(
        {"metadata-danceman251": {"metadata": metadata, "files": [{"name": "danceman251_djvu.txt"}]}},
        {"text-danceman251": f"{PARA}\n\n{PARA}\n\n{PARA}\n\n{PARA}"},
    )


def test_requires_identifiers(fake_http, isolated_data):
    with pytest.raises(SourceError) as exc:
        IaFetcher(_spec(), fake_http({})).fetch(limit=1)
    assert exc.value.code == "no_identifiers"


def test_writes_with_default_acts_and_note(fake_http, isolated_data):
    spec = _spec(IaIdentifier(id="danceman251", work="The Code of Terpsichore", choreographer="Carlo Blasis"))
    metadata = {"title": "The code of Terpsichore", "creator": "Blasis, Carlo", "date": "1830-01-01"}
    report = IaFetcher(spec, _http(fake_http, metadata)).fetch(limit=1)
    assert report.written == 1
    doc = load_markdown(Path(isolated_data) / "raw" / "ballet" / "internet_archive_danceman251.md", "ballet")
    assert doc.meta["acts"] == spec.default_acts
    assert doc.meta["premiere_year"] == 1830
    assert "幕数按" in doc.meta["version_note"]


def test_conflicting_license_refused(fake_http, isolated_data):
    spec = _spec(IaIdentifier(id="danceman251", work="X", choreographer="Y", premiere_year=1830))
    metadata = {"title": "X", "creator": "Y", "date": "1830", "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"}
    report = IaFetcher(spec, _http(fake_http, metadata)).fetch(limit=1)
    assert report.written == 0
    assert report.refused[0].reason.startswith("license_conflict")
