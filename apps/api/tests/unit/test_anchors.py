from ac_api.curation.anchors import build_anchor, validate_anchor
from ac_api.domain.models import Anchor
from ac_api.rag.ingest.loaders.md import load_markdown
from ac_api.rag.ingest.chunkers import get_chunker
from ac_api.config import load_config
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _chunks(domain: str, name: str):
    doc = load_markdown(FIXTURES / domain / name, domain)
    drafts = get_chunker(load_config().domain(domain).chunker).split(doc, load_config().domain(domain))
    return doc, drafts


def test_music_anchor_within_duration():
    doc, drafts = _chunks("music", "beethoven9_1824.md")
    anchor = build_anchor("music", drafts, doc.meta)
    assert anchor is not None
    assert anchor.kind == "listen"
    assert validate_anchor("music", anchor, doc.meta)[0] is True


def test_music_anchor_rejected_when_out_of_duration():
    bad = Anchor(kind="listen", label="x", spec={"from_s": 0, "to_s": 99999})
    ok, why = validate_anchor("music", bad, {"duration_s": 100})
    assert ok is False and "超出" in why


def test_ballet_anchor_respects_act_count():
    doc, drafts = _chunks("ballet", "nutcracker_1892.md")
    anchor = build_anchor("ballet", drafts, doc.meta)
    assert anchor is not None and anchor.spec["act"] <= doc.meta["acts"]


def test_ballet_anchor_rejected_when_act_too_large():
    ok, _ = validate_anchor("ballet", Anchor(kind="watch", label="x", spec={"act": 5}), {"acts": 2})
    assert ok is False
