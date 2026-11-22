"""MusicBrainz：曲目结构 + 音轨时长。

时长必须来自音轨（缺 length 就做不出"听哪一段"，整条拒绝）；
一个 release = 一个 doc，不同 release = 不同 doc（同乐章不同版本必须分块）。
"""

from __future__ import annotations

from typing import Any

from ac_api.rag.ingest.sources.base import FetchReport, Http, SourceError, mmss, write_doc
from ac_api.sources import SourceSpec, get_source

BASE = "https://musicbrainz.org/ws/2"


def _artist_names(credits: list[Any]) -> list[str]:
    names: list[str] = []
    for credit in credits or []:
        if isinstance(credit, dict) and credit.get("name"):
            names.append(str(credit["name"]))
    return names


class MusicBrainzFetcher:
    def __init__(self, spec: SourceSpec | None = None, http: Http | None = None) -> None:
        self.spec = spec or get_source("musicbrainz")
        self.http = http or Http(self.spec)

    def _tracks(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        tracks: list[dict[str, Any]] = []
        for medium in data.get("media") or []:
            tracks.extend(medium.get("tracks") or [])
        return tracks

    def _body(self, data: dict[str, Any], tracks: list[dict[str, Any]], meta: dict[str, Any]) -> str:
        composer = meta["composer"]
        label = ", ".join(
            str((info.get("label") or {}).get("name"))
            for info in data.get("label-info") or []
            if (info.get("label") or {}).get("name")
        )
        release_line = f"发行：{label or '未标注'}；{data.get('date') or '发行年未标注'}。"
        seen: set[str] = set()
        titles = [str(t.get("title") or "") for t in tracks]
        duplicated = len(set(titles)) < len(titles)

        sections: list[str] = []
        offset = 0
        for index, track in enumerate(tracks, start=1):
            length_s = int(track["length"]) // 1000
            title = str(track.get("title") or "")
            suffix = "" if (duplicated or not title or title in seen) else f" · {title}"
            seen.add(title)
            sections.append(
                f"## 第{index}乐章{suffix}\n"
                f'<!-- section-meta: {{"movement": {index}, "movement_from_s": {offset}, '
                f'"movement_duration_s": {length_s}}} -->\n'
                f"录音：{data.get('title')}；演奏：{composer}；本轨时长 {mmss(length_s)}。\n"
                f"{release_line}\n"
            )
            offset += length_s
        return "\n".join(sections)

    def fetch(self, limit: int = 5, query: str | None = None, dry_run: bool = False) -> FetchReport:
        report = FetchReport(source=self.spec.name, domain=self.spec.domain, dry_run=dry_run)
        keyword = query or "symphony"
        search = self.http.get_json(
            f"{BASE}/release",
            params={"query": keyword, "fmt": "json", "limit": min(limit * 3, 30)},
            cache_key=f"search-{keyword}",
        )
        releases = (search.get("releases") or [])[: limit * 3]
        report.candidates = len(releases)

        for release in releases:
            if report.written >= limit:
                break
            mbid = release.get("id")
            if not mbid:
                continue
            try:
                data = self.http.get_json(
                    f"{BASE}/release/{mbid}",
                    params={"inc": "recordings+artist-credits+labels", "fmt": "json"},
                    cache_key=f"release-{mbid}",
                )
                tracks = self._tracks(data)
                if not tracks:
                    report.refuse(mbid, "no_tracks")
                    continue
                if len(tracks) > self.spec.max_tracks:
                    report.refuse(mbid, "too_many_tracks")
                    continue
                if any(not track.get("length") for track in tracks):
                    report.refuse(mbid, "missing_track_length")
                    continue

                composers = _artist_names(data.get("artist-credit") or [])
                if not composers:
                    report.refuse(mbid, "missing_composer")
                    continue
                meta: dict[str, Any] = {
                    "composer": " & ".join(composers),
                    "work": data.get("title", ""),
                    "duration_s": sum(int(t["length"]) for t in tracks) // 1000,
                    "display_zh": f"《{data.get('title', '')}》",
                    "title_orig": data.get("title", ""),
                }
                date = str(data.get("date") or "")
                if len(date) >= 4 and date[:4].isdigit():
                    meta["release_year"] = int(date[:4])
                if data.get("barcode"):
                    meta["barcode"] = data["barcode"]

                doc = write_doc(
                    self.spec,
                    external_id=mbid,
                    title=data.get("title", ""),
                    body=self._body(data, tracks, meta),
                    meta=meta,
                    source_url=f"https://musicbrainz.org/release/{mbid}",
                    dry_run=dry_run,
                )
                if doc.changed or dry_run:
                    report.written += 1
                else:
                    report.skipped += 1
                if dry_run:
                    report.preview.append({"doc_id": doc.doc_id, "head": doc.text[:700]})
            except SourceError as exc:
                report.refuse(mbid, exc.code)
        return report
