"""源探针：只打一条样本，打印映射命中率与将写入的 front matter。默认不落盘。

用法：
  make probe SOURCE=met
  make probe SOURCE=musicbrainz QUERY="symphony beethoven"
  make probe SOURCE=met WRITE=1        # 才会真的写一份进 data/raw
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ac_api.rag.ingest.sources import get_fetcher  # noqa: E402
from ac_api.rag.ingest.sources.base import SourceError  # noqa: E402
from ac_api.sources import get_source  # noqa: E402


def main(source: str, query: str | None, write: bool) -> int:
    spec = get_source(source)
    print(f"== {spec.name} → {spec.domain} · license={spec.license} · {spec.rate_limit_rps} rps")
    try:
        report = get_fetcher(source).fetch(limit=1, query=query, dry_run=not write)
    except SourceError as exc:
        print(f"error[{exc.code}] {exc.message}")
        return 3

    print(f"  candidates={report.candidates} written={report.written} dry_run={report.dry_run}")
    if report.refused:
        for item in report.refused[:5]:
            print(f"  refused {item.external_id}: {item.reason}")
    if report.missing_meta:
        print(f"  missing_meta={report.missing_meta}")

    for preview in report.preview:
        head = preview["head"]
        meta_line = next((line for line in head.splitlines() if line.startswith("meta: ")), "meta: {}")
        meta = json.loads(meta_line[len("meta: ") :])
        hit = [key for key in spec.require_meta if meta.get(key) not in (None, "")]
        print(f"\n  doc_id={preview['doc_id']}  映射命中 {len(hit)}/{len(spec.require_meta)}：{hit}")
        print("  " + "-" * 56)
        for line in head.splitlines()[:14]:
            print("  " + line)
    return 0 if (report.written or report.dry_run) else 2


if __name__ == "__main__":
    args = dict(arg.split("=", 1) for arg in sys.argv[1:] if "=" in arg)
    raise SystemExit(
        main(
            args.get("SOURCE", "met"),
            args.get("QUERY"),
            args.get("WRITE", "") in ("1", "true", "yes"),
        )
    )
