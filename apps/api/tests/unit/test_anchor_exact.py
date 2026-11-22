from ac_api.curation.anchors import build_music_anchor
from ac_api.domain.models import Chunk, Locator


def _chunk(movement: int, from_s: int, dur: int) -> Chunk:
    return Chunk(
        chunk_id=f"c{movement}",
        doc_id="d",
        domain="music",
        text="x" * 80,
        locator=Locator(doc_title="t"),
        metadata={
            "movement": movement,
            "movement_from_s": from_s,
            "movement_duration_s": dur,
            "duration_s": 3000,
        },
    )


def test_exact_timing_preferred_over_proportional():
    chunks = [_chunk(1, 0, 600), _chunk(2, 600, 500)]
    anchor = build_music_anchor(chunks, {"duration_s": 3000})
    assert anchor is not None
    assert anchor.spec["approx"] is False
    assert anchor.spec["from_s"] == 600
    assert anchor.spec["to_s"] == 780  # 180 秒上限
    assert "约" not in anchor.label


def test_falls_back_to_proportional_when_no_exact_data():
    chunks = [_chunk(1, 0, 600)]  # 只有乐章 1，没有乐章 2
    anchor = build_music_anchor(chunks, {"duration_s": 2400})
    assert anchor is not None
    assert anchor.spec["approx"] is False  # 乐章 1 自己就有精确时长
    no_exact = [
        Chunk(
            chunk_id="c1",
            doc_id="d",
            domain="music",
            text="x" * 80,
            locator=Locator(doc_title="t"),
            metadata={"movement": 1},
        )
    ]
    anchor = build_music_anchor(no_exact, {"duration_s": 2400})
    assert anchor is not None and anchor.spec["approx"] is True
