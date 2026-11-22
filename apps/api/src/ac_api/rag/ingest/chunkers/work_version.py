"""音乐：按 曲目 × 录音版本 切分。同一乐章不同版本必须是不同 chunk。"""

from __future__ import annotations

import re

from ac_api.config import DomainSpec
from ac_api.domain.models import ChunkDraft
from ac_api.rag.ingest.chunkers.base import build_drafts, cn_number
from ac_api.rag.ingest.loaders.md import LoadedDoc

MOV_RE = re.compile(r"第([一二三四五六七八九十\d]+)乐章\s*[·:：\-]?\s*(.*)$")


class WorkVersionChunker:
    name = "work_version"

    def split(self, doc: LoadedDoc, spec: DomainSpec) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for section in doc.sections:
            heading = section.heading or ""
            meta = dict(doc.meta)
            match = MOV_RE.search(heading)
            if match:
                movement = cn_number(match.group(1))
                if movement is not None:
                    meta["movement"] = movement
                subtitle = (match.group(2) or "").strip()
                if subtitle:
                    meta["movement_name"] = subtitle
            parent = f"{doc.doc_id}:work"
            drafts.extend(
                build_drafts(
                    doc, section, metadata=meta, parent_heading=parent, domain=doc.domain
                )
            )
        return drafts
