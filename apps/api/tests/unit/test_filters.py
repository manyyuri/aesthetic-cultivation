import pytest

from ac_api.config import load_config
from ac_api.rag.retrieve.filters import FilterError, relaxations, validate_filter

SPEC = load_config().domain("ballet")


def test_valid_filter_normalized():
    out = validate_filter(SPEC, {"premiere_year": "1892"})
    assert out == {"premiere_year": {"$eq": 1892}}


def test_unknown_key_rejected_with_allowed_list():
    with pytest.raises(FilterError) as exc:
        validate_filter(SPEC, {"dynasty": "唐"})
    assert "dynasty" in str(exc.value)
    assert exc.value.details["allowed"]


def test_type_and_range_checked():
    with pytest.raises(FilterError):
        validate_filter(SPEC, {"premiere_year": "很久以前"})
    with pytest.raises(FilterError):
        validate_filter(SPEC, {"premiere_year": 1200})
    with pytest.raises(FilterError):
        validate_filter(SPEC, {"choreographer": "x" * 80})


def test_empty_filter_is_none_and_relaxations():
    assert validate_filter(SPEC, None) is None
    assert len(relaxations(SPEC, {"act": 2})) == 1
