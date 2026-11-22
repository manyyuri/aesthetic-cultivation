import pytest

from ac_api.sources import SourceConfigError, load_from_dict, normalize_license


def _base(**over):
    sources = {
        "met": {
            "domain": "art",
            "fetcher": "met",
            "license": "CC0-1.0",
            "require_meta": ["object_id", "museum", "technique", "period"],
            **over,
        }
    }
    return {"allow": {"licenses": ["CC0-1.0", "public-domain", "CC-BY-SA-4.0"]}, "sources": sources}


def test_normalize_license_variants():
    assert normalize_license("excerpt · CC BY-SA 4.0") == "CC-BY-SA-4.0"
    assert normalize_license("cc0") == "CC0-1.0"
    assert normalize_license("Public Domain") == "public-domain"
    assert normalize_license(None) is None


def test_bad_license_rejected_at_load_time():
    with pytest.raises(SourceConfigError) as exc:
        load_from_dict(_base(license="CC-BY-NC-4.0"))
    assert "不在白名单" in str(exc.value)


def test_require_meta_must_cover_domain_required_meta():
    with pytest.raises(SourceConfigError) as exc:
        load_from_dict(_base(require_meta=["object_id"]))
    assert "require_meta" in str(exc.value)


def test_unknown_domain_and_bad_name():
    with pytest.raises(SourceConfigError):
        load_from_dict(_base(domain="opera"))
    bad = _base()
    bad["sources"] = {"MET": bad["sources"]["met"]}
    with pytest.raises(SourceConfigError):
        load_from_dict(bad)
