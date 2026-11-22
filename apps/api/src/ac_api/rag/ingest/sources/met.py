"""Met Collection API：CC0 作品元数据 + CC0 图。

只收 isPublicDomain=true 的对象（否则 license 字段会说谎）。
"""

from __future__ import annotations

from typing import Any

from ac_api.rag.ingest.sources.base import (
    FetchReport,
    Http,
    SourceError,
    write_doc,
)
from ac_api.sources import SourceSpec, get_source

# /v1/search 已于 2026-10-01 退役（410），搜索走 v1.1（Elasticsearch），对象详情仍在 v1
SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
MUSEUM = "The Metropolitan Museum of Art"


class MetFetcher:
    def __init__(self, spec: SourceSpec | None = None, http: Http | None = None) -> None:
        self.spec = spec or get_source("met")
        self.http = http or Http(self.spec)

    def _body(self, data: dict[str, Any], meta: dict[str, Any]) -> str:
        credit = data.get("creditLine") or ""
        culture = data.get("culture") or "未标注"
        period = data.get("period") or data.get("objectDate") or "未标注"
        return f"""## 作品

{data.get('title', '')}，{meta.get('artist', '佚名')}，{data.get('objectDate', '年代未标注')}。
{data.get('medium', '')}。{credit}

## 形制与分类

部门：{data.get('department', '未标注')}；分类：{data.get('classification', '未标注')}；
文化：{culture}；时期：{period}。

## 著录

馆藏编号 {data['objectID']}，现藏{meta['museum']}。原始记录：{data['objectURL']}
"""

    def fetch(self, limit: int = 10, query: str | None = None, dry_run: bool = False) -> FetchReport:
        report = FetchReport(source=self.spec.name, domain=self.spec.domain, dry_run=dry_run)
        keyword = query or "painting"
        search = self.http.get_json(
            SEARCH,
            params={"q": keyword, "hasImages": "true", "isPublicDomain": "true"},
            cache_key=f"search-{keyword}",
        )
        # v1.1 的搜索不保证遵守 isPublicDomain 过滤（实测会返回非公版对象），
        # 所以按 10 倍取样、逐条在详情里复核，宁可多请求几次
        ids = (search.get("objectIDs") or [])[: min(limit * 10, 200)]
        report.candidates = len(ids)

        for object_id in ids:
            if report.written >= limit:
                break
            try:
                data = self.http.get_json(f"{OBJECT}/{object_id}", cache_key=f"object-{object_id}")
                if not data.get("isPublicDomain"):
                    report.refuse(object_id, "not_public_domain")
                    continue
                if not data.get("objectURL"):
                    report.refuse(object_id, "missing_source_url")
                    continue

                meta: dict[str, Any] = {
                    "object_id": str(data["objectID"]),
                    "museum": data.get("repository") or MUSEUM,
                    "technique": data.get("medium") or "",
                    "period": data.get("period") or data.get("objectDate") or "",
                    "material": data.get("classification") or "",
                    "image_url": data.get("primaryImageSmall") or None,
                    "display_zh": f"《{data.get('title', '').strip()}》",
                    "title_orig": data.get("title", "").strip(),
                }
                if data.get("artistDisplayName"):
                    meta["artist"] = data["artistDisplayName"]

                doc = write_doc(
                    self.spec,
                    external_id=data["objectID"],
                    title=f"{data.get('title', '').strip()}（{data.get('artistDisplayName') or '佚名'}）",
                    body=self._body(data, meta),
                    meta=meta,
                    source_url=data["objectURL"],
                    dry_run=dry_run,
                )
                if doc.changed or dry_run:
                    report.written += 1
                else:
                    report.skipped += 1
                if dry_run:
                    report.preview.append({"doc_id": doc.doc_id, "head": doc.text[:700]})
            except SourceError as exc:
                report.refuse(object_id, exc.code)
        return report
