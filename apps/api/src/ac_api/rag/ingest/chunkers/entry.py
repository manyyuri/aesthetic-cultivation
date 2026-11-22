"""美术：按作品条目切分。一条目绝不跨两个作品。"""

from __future__ import annotations

from ac_api.config import DomainSpec
from ac_api.domain.models import ChunkDraft
from ac_api.rag.ingest.chunkers.base import build_drafts
from ac_api.rag.ingest.loaders.md import LoadedDoc


class EntryChunker:
    name = "entry"

    def split(self, doc: LoadedDoc, spec: DomainSpec) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for section in doc.sections:
            meta = dict(doc.meta)
            if section.heading:
                meta.setdefault("entry_title", section.heading)
            parent = f"{doc.doc_id}:{meta.get('object_id') or 'entry'}"
            drafts.extend(
                build_drafts(
                    doc, section, metadata=meta, parent_heading=parent, domain=doc.domain
                )
            )
        return drafts

