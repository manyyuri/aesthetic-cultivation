"""Markdown 载入：解析 front matter + `## ` 小节。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ac_api.domain.models import normalize_text

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
SECTION_META_RE = re.compile(r"^\s*<!--\s*section-meta:\s*(\{.*\})\s*-->\s*$")
RESERVED = {
    "meta", "title", "doc_id", "domain", "source_url", "license", "source_priority",
    "source", "external_id", "retrieved_at",
}


class Section(BaseModel):
    heading: str | None = None
    level: int = 2
    text: str
    # 小节级元数据：`<!-- section-meta: {"movement_duration_s": 480} -->` 紧跟标题时被吸收
    meta: dict[str, Any] = Field(default_factory=dict)


class LoadedDoc(BaseModel):
    doc_id: str
    title: str
    domain: str
    source_url: str | None = None
    license: str | None = None
    source_priority: str = "secondary_web"
    source: str = "manual"
    external_id: str | None = None
    retrieved_at: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    sections: list[Section] = Field(default_factory=list)
    path: str = ""


def _parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    match = FM_RE.match(raw)
    if not match:
        return {}, raw
    data: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not value:
            continue
        if value.startswith("{") or value.startswith("["):
            try:
                data[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if value.lower() in ("true", "false"):
            data[key] = value.lower() == "true"
        elif re.fullmatch(r"-?\d+", value):
            data[key] = int(value)
        elif re.fullmatch(r"-?\d+\.\d+", value):
            data[key] = float(value)
        else:
            data[key] = value.strip('"').strip("'")
    return data, raw[match.end() :]


def _split_sections(body: str) -> list[Section]:
    sections: list[Section] = []
    current: Section | None = None
    buf: list[str] = []

    def flush() -> None:
        if current is None:
            return
        current.text = normalize_text("\n".join(buf))
        if current.text:
            sections.append(current)

    for line in body.splitlines():
        stripped = line.strip()
        heading = HEADING_RE.match(stripped)
        if heading:
            flush()
            current = Section(heading=heading.group(2).strip(), level=len(heading.group(1)), text="")
            buf = []
            continue
        # 紧跟标题的 section-meta 注释：吸收成小节元数据，不进入正文
        meta_match = SECTION_META_RE.match(stripped)
        if meta_match and current is not None and not buf and not current.meta:
            try:
                current.meta = json.loads(meta_match.group(1))
                continue
            except json.JSONDecodeError:
                pass
        buf.append(line)
    flush()
    return sections


def load_markdown(path: Path, domain: str) -> LoadedDoc:
    raw = path.read_text(encoding="utf-8")
    fm, body = _parse_front_matter(raw)
    sections = _split_sections(body)
    if not sections:
        sections = [Section(heading=None, text=normalize_text(body))]
    meta = fm.get("meta") or {}
    for key, value in fm.items():
        if key not in RESERVED:
            meta.setdefault(key, value)
    return LoadedDoc(
        doc_id=str(fm.get("doc_id") or path.stem),
        title=str(fm.get("title") or path.stem),
        domain=str(fm.get("domain") or domain),
        source_url=fm.get("source_url"),
        license=fm.get("license"),
        source_priority=str(fm.get("source_priority") or "secondary_web"),
        source=str(fm.get("source") or "manual"),
        external_id=str(fm["external_id"]) if fm.get("external_id") is not None else None,
        retrieved_at=str(fm["retrieved_at"]) if fm.get("retrieved_at") else None,
        meta=meta,
        sections=sections,
        path=str(path),
    )
