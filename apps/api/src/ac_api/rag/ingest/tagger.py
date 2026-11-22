"""元数据抽取：规则优先。缺必填字段不是降级，是入库失败。"""

from __future__ import annotations

from typing import Any

from ac_api.config import DomainSpec
from ac_api.domain.models import ChunkDraft

INT_FIELDS = {"premiere_year", "act", "movement", "duration_s", "release_year", "acts"}


def tag(draft: ChunkDraft, spec: DomainSpec) -> tuple[dict[str, Any], list[str]]:
    meta = dict(draft.metadata)
    for key in INT_FIELDS & set(meta):
        value = meta[key]
        if isinstance(value, str) and value.strip().isdigit():
            meta[key] = int(value.strip())
    missing = [
        key
        for key in spec.required_meta
        if meta.get(key) is None or (isinstance(meta.get(key), str) and not meta[key].strip())
    ]
    return meta, missing
