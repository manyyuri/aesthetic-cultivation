from pathlib import Path

from ac_api.config import load_config
from ac_api.rag.ingest.chunkers import get_chunker
from ac_api.rag.ingest.loaders.md import load_markdown

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_ballet_act_scene_keeps_act_metadata_and_boundaries():
    doc = load_markdown(FIXTURES / "ballet" / "nutcracker_1892.md", "ballet")
    drafts = get_chunker("act_scene").split(doc, load_config().domain("ballet"))
    assert drafts
    acts = {d.metadata.get("act") for d in drafts}
    assert acts == {1, 2}
    assert len({d.parent_heading for d in drafts}) == 2
    assert all(len(d.text) >= 40 for d in drafts)


def test_music_work_version_numbers_movements():
    doc = load_markdown(FIXTURES / "music" / "beethoven9_1824.md", "music")
    drafts = get_chunker("work_version").split(doc, load_config().domain("music"))
    movements = [d.metadata.get("movement") for d in drafts]
    assert movements[:4] == [1, 2, 3, 4]
    assert all(d.metadata["duration_s"] == 4200 for d in drafts)


def test_art_entry_binds_object_id():
    doc = load_markdown(FIXTURES / "art" / "monet_impression_sunrise.md", "art")
    drafts = get_chunker("entry").split(doc, load_config().domain("art"))
    assert drafts
    assert all(d.metadata["object_id"] == "monet-impression-sunrise" for d in drafts)
