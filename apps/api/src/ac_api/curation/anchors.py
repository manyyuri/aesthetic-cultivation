"""动作锚点：让"模拟体验"可执行。校验不过 ⇒ 换候选，不是降级。"""

from __future__ import annotations

import re

from ac_api.domain.models import Anchor, Chunk

CN_DIGITS = "零一二三四五六七八九"
SENT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?]?")


def _cn(n: int) -> str:
    return {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}.get(n, str(n))


def mmss(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _heading_of(chunk) -> str | None:
    """Chunk 的标题在 locator.anchor；ChunkDraft 在 heading。两处都支持，测试才好写。"""
    locator = getattr(chunk, "locator", None)
    if locator is not None:
        return getattr(locator, "anchor", None)
    return getattr(chunk, "heading", None)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.findall(text) if len(s.strip()) >= 8]


def _cue(sentence: str) -> str:
    """压成一个 16 字以内的短句，展签上读起来才像"看这几处"，而不是把整句抄一遍。"""
    text = sentence
    for sep in ("：", ":"):
        if sep in text:
            text = text.split(sep, 1)[1]
    text = text.split("，")[0]
    return text.strip("。！？：:； ")[:16]


def build_art_anchor(chunks: list[Chunk], meta: dict) -> Anchor | None:
    cue = None
    for sentence in (s for chunk in chunks for s in _sentences(chunk.text)):
        if any(word in sentence for word in ("笔触", "颜色", "色", "光", "线", "构图", "旋涡")):
            cue = sentence
            break
    if not cue:
        sentences = [s for chunk in chunks for s in _sentences(chunk.text)]
        cue = sentences[0] if sentences else None
    if not cue:
        return None
    short = _cue(cue)
    return Anchor(kind="look", label=f"看这几处：{short}", spec={"cue": short, "region": None})


def build_music_anchor(chunks: list[Chunk], meta: dict) -> Anchor | None:
    duration = meta.get("duration_s")
    if not isinstance(duration, int) or duration <= 0:
        return None
    movements = sorted({c.metadata.get("movement") for c in chunks if c.metadata.get("movement")})
    if movements:
        total = len(movements)
        pick: int | None = movements[1] if len(movements) >= 2 else movements[0]
        span = duration / total
        from_s = int((int(pick) - 1) * span)
        to_s = min(int(from_s + min(180, span)), duration)
    else:
        # 没有乐章结构（如变奏曲）：给"开头三分钟"，不假装有乐章编号
        pick = None
        from_s, to_s = 0, min(180, duration)
    if to_s - from_s < 60:
        return None
    label = f"听第{_cn(int(pick))}乐章 · {mmss(from_s)}–{mmss(to_s)}" if pick else f"听开头 · {mmss(from_s)}–{mmss(to_s)}"
    spec = {"from_s": from_s, "to_s": to_s, "approx": True}
    if pick:
        spec["movement"] = int(pick)
    return Anchor(kind="listen", label=label, spec=spec)


def build_ballet_anchor(chunks: list[Chunk], meta: dict) -> Anchor | None:
    acts = meta.get("acts")
    if not isinstance(acts, int) or acts < 1:
        return None
    available = sorted({c.metadata.get("act") for c in chunks if isinstance(c.metadata.get("act"), int)})
    if not available:
        return None
    pick = 2 if 2 in available else available[0]
    if pick > acts:
        return None
    scene = next(
        (c.metadata.get("scene") for c in chunks if c.metadata.get("act") == pick and c.metadata.get("scene")),
        None,
    )
    heading = next((_heading_of(c) for c in chunks if c.metadata.get("act") == pick and _heading_of(c)), None)
    tail = scene or (heading.split("·")[-1].strip() if heading and "·" in heading else None)
    label = f"看第{_cn(pick)}幕" + (f" · {tail}" if tail else "")
    return Anchor(kind="watch", label=label, spec={"act": pick, "cue": tail})


BUILDERS = {"art": build_art_anchor, "music": build_music_anchor, "ballet": build_ballet_anchor}


def build_anchor(domain: str, chunks: list[Chunk], meta: dict) -> Anchor | None:
    builder = BUILDERS.get(domain)
    if not builder:
        return None
    anchor = builder(chunks, meta)
    if not anchor:
        return None
    ok, _ = validate_anchor(domain, anchor, meta)
    return anchor if ok else None


def validate_anchor(domain: str, anchor: Anchor, meta: dict) -> tuple[bool, str]:
    spec = anchor.spec or {}
    if domain == "music":
        duration = meta.get("duration_s")
        if not isinstance(duration, int):
            return False, "缺 duration_s"
        to_s, from_s = spec.get("to_s"), spec.get("from_s")
        if not isinstance(to_s, int) or not isinstance(from_s, int):
            return False, "锚点缺 from_s/to_s"
        if to_s > duration:
            return False, f"锚点超出曲目时长（{to_s}s > {duration}s）"
        if not 60 <= to_s - from_s <= 300:
            return False, "片段长度不在 60–300 秒"
    if domain == "ballet":
        acts = meta.get("acts")
        act = spec.get("act")
        if not isinstance(acts, int) or not isinstance(act, int):
            return False, "缺 acts 或 act"
        if act > acts:
            return False, f"幕次超出（{act} > {acts}）"
    if domain == "art":
        if not spec.get("cue"):
            return False, "美术锚点缺 cue"
    return True, ""
