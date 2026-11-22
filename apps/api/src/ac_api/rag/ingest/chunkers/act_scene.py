"""芭蕾：按 版本 × 幕 × 场 切分。幕/场是硬边界，段落不跨场。"""

from __future__ import annotations

import re

from ac_api.config import DomainSpec
from ac_api.domain.models import ChunkDraft
from ac_api.rag.ingest.chunkers.base import build_drafts, cn_number
from ac_api.rag.ingest.loaders.md import LoadedDoc

ACT_RE = re.compile(r"第([一二三四五六七八九十\d]+)幕\s*[·:：\-]?\s*(.*)$")


class ActSceneChunker:
    name = "act_scene"

    def split(self, doc: LoadedDoc, spec: DomainSpec) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        current_act: int | None = doc.meta.get("act") if isinstance(doc.meta.get("act"), int) else None
        for section in doc.sections:
            heading = section.heading or ""
            act, scene = current_act, None
            match = ACT_RE.search(heading)
            if match:
                act = cn_number(match.group(1))
                scene = (match.group(2) or "").strip() or None
            meta = dict(doc.meta)
            if act is not None:
                meta["act"] = act
                current_act = act
            if scene:
                meta["scene"] = scene
            parent = f"{doc.doc_id}:act{act}" if act is not None else doc.doc_id
            drafts.extend(
                build_drafts(
                    doc, section, metadata=meta, parent_heading=parent, domain=doc.domain
                )
            )
        return drafts
