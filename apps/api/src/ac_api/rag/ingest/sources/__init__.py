from __future__ import annotations

from ac_api.rag.ingest.sources.base import Fetcher, FetchReport, SourceError
from ac_api.rag.ingest.sources.ia import IaFetcher
from ac_api.rag.ingest.sources.met import MetFetcher
from ac_api.rag.ingest.sources.musicbrainz import MusicBrainzFetcher

FETCHERS: dict[str, type] = {
    "met": MetFetcher,
    "musicbrainz": MusicBrainzFetcher,
    "ia": IaFetcher,
}


def get_fetcher(name: str) -> Fetcher:
    if name not in FETCHERS:
        raise SourceError("unknown_fetcher", f"未知 fetcher：{name}（可选：{', '.join(sorted(FETCHERS))}）")
    return FETCHERS[name]()  # type: ignore[return-value]


__all__ = ["FETCHERS", "Fetcher", "FetchReport", "SourceError", "get_fetcher"]
