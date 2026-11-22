"""Internet Archive：只接人工挑过的 identifier。

19 世纪扫描件往往没有 licenseurl，公版状态没法从字段判定 —— 所以不自动判定，
由人在 config/sources.yaml 里写好 license 与领域元数据，fetcher 只负责搬运。
"""

from __future__ import annotations

import re
from typing import Any

from ac_api.rag.ingest.sources.base import FetchReport, Http, SourceError, write_doc
from ac_api.sources import IaIdentifier, SourceSpec, get_source, normalize_license

BASE = "https://archive.org"
PD_LICENSES = {"public-domain", "Public-Domain-Mark-1.0", "CC0-1.0"}
YEAR_RE = re.compile(r"(1[5-9]\d{2}|20\d{2})")
PARA_RE = re.compile(r"\n{2,}")


class IaFetcher:
    def __init__(self, spec: SourceSpec | None = None, http: Http | None = None) -> None:
        self.spec = spec or get_source("internet_archive")
        self.http = http or Http(self.spec)

    def _sections(self, text: str) -> str:
        budget = max(self.spec.max_chars, 600)
        paragraphs = [p.strip().replace("\n", " ") for p in PARA_RE.split(text) if len(p.strip()) >= 80]
        picked: list[str] = []
        used = 0
        for para in paragraphs:
            if used + len(para) > budget:
                break
            picked.append(para)
            used += len(para)
        if len(picked) < 2:
            raise SourceError("body_too_short", "全文可用段落不足，无法组成两段以上摘录")
        chunks = [picked[i::3] for i in range(3)]
        blocks = []
        for index, chunk in enumerate(chunks, start=1):
            if not chunk:
                continue
            blocks.append(f"## 摘录{index}\n\n" + "\n\n".join(chunk))
        return "\n\n".join(blocks)

    def _conflicting_license(self, metadata: dict[str, Any]) -> str | None:
        raw = metadata.get("licenseurl") or metadata.get("rights") or ""
        normalized = normalize_license(raw) if raw else None
        if not normalized:
            return None
        return None if normalized in PD_LICENSES else normalized

    def fetch(self, limit: int = 5, query: str | None = None, dry_run: bool = False) -> FetchReport:
        report = FetchReport(source=self.spec.name, domain=self.spec.domain, dry_run=dry_run)
        if not self.spec.identifiers:
            raise SourceError(
                "no_identifiers",
                "IA 源需要人工在 config/sources.yaml 的 identifiers 里填条目：公版状态无法从字段判定",
            )
        entries: list[IaIdentifier] = self.spec.identifiers[:limit]
        report.candidates = len(entries)

        for entry in entries:
            try:
                payload = self.http.get_json(
                    f"{BASE}/metadata/{entry.id}", cache_key=f"metadata-{entry.id}"
                )
                metadata = payload.get("metadata") or {}
                conflict = self._conflicting_license(metadata)
                if conflict:
                    report.refuse(entry.id, f"license_conflict:{conflict}")
                    continue

                files = payload.get("files") or []
                text_file = next(
                    (f["name"] for f in files if str(f.get("name", "")).endswith("_djvu.txt")), None
                )
                if not text_file:
                    report.refuse(entry.id, "no_plain_text")
                    continue
                text = self.http.get_text(
                    f"{BASE}/download/{entry.id}/{text_file}", cache_key=f"text-{entry.id}"
                )

                year = entry.premiere_year
                if year is None:
                    match = YEAR_RE.search(str(metadata.get("date") or ""))
                    year = int(match.group(1)) if match else None
                acts = entry.acts or self.spec.default_acts
                meta: dict[str, Any] = {
                    "work": entry.work or str(metadata.get("title") or ""),
                    "choreographer": entry.choreographer or str(metadata.get("creator") or ""),
                    "premiere_year": year,
                    "acts": acts,
                    "source_priority": self.spec.source_priority,
                    "display_zh": f"《{entry.work or metadata.get('title') or entry.id}》",
                }
                note = entry.version_note or f"{year or '年代未标注'} 年资料，幕数按 {acts} 推定"
                meta["version_note"] = note

                doc = write_doc(
                    self.spec,
                    external_id=entry.id,
                    title=str(metadata.get("title") or entry.work or entry.id),
                    body=self._sections(text),
                    meta=meta,
                    source_url=f"{BASE}/details/{entry.id}",
                    license_id=entry.license,
                    dry_run=dry_run,
                )
                if doc.changed or dry_run:
                    report.written += 1
                else:
                    report.skipped += 1
                if dry_run:
                    report.preview.append({"doc_id": doc.doc_id, "head": doc.text[:700]})
            except SourceError as exc:
                report.refuse(entry.id, exc.code)
        return report
