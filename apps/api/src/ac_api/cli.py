"""命令行入口：Makefile 调它，不进 HTTP。"""

from __future__ import annotations

import argparse
import json
import sys

from ac_api.config import UnknownDomain, load_config
from ac_api.rag.index.builder import NoChunks, build_index, rollback
from ac_api.rag.ingest.pipeline import ingest_domain
from ac_api.rag.retrieve.pipeline import RetrieveError, Retriever
from ac_api.store.db import init_db


def _print_report(report) -> None:
    print(f"domain={report.domain}")
    print(
        f"  docs  total={report.docs_total} added={report.docs_added} "
        f"replaced={report.docs_replaced} skipped={report.docs_skipped}"
    )
    print(f"  chunks total={report.chunks_total} rejected={report.chunks_rejected}")
    for reason, count in sorted(report.rejected_reasons.items()):
        print(f"    - {reason}: {count}")


def cmd_ingest(args: argparse.Namespace) -> int:
    report = ingest_domain(args.domain, force=args.force)
    _print_report(report)
    return 2 if report.chunks_rejected else 0


def cmd_index(args: argparse.Namespace) -> int:
    manifest = build_index(args.domain)
    print(json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2))
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    rollback(args.domain, args.version)
    print(f"active → {args.version}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from ac_api.domain.models import RetrieveRequest

    retriever = Retriever()
    response = retriever.retrieve(
        RetrieveRequest(domain=args.domain, query=args.query, top_k=args.top_k)
    )
    print(f"status={response.evidence_status} index={response.index_version} latency={response.latency_ms}ms")
    if response.missing_hint:
        print(f"missing_hint={response.missing_hint}")
    for chunk in response.chunks:
        print(f"\n[{chunk.citation_id}] rerank={chunk.scores.get('rerank')} {chunk.source}")
        print(f"  {chunk.content[:220].replace(chr(10), ' ')}…")
    return 0 if response.chunks else 3


def cmd_issue_build(args: argparse.Namespace) -> int:
    from ac_api.orchestrator.core import build_issue

    result = build_issue(args.date, kind=args.kind)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)[:4000])
    return 0 if result.status in ("ready", "partial") else 1


def cmd_issue_deliver(args: argparse.Namespace) -> int:
    from ac_api.orchestrator.core import deliver_issue

    report = deliver_issue(args.date, channels=[args.channel])
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if report.delivered else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ac")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("--domain", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("index")
    p.add_argument("--domain", required=True)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("rollback")
    p.add_argument("--domain", required=True)
    p.add_argument("--version", required=True)
    p.set_defaults(func=cmd_rollback)

    p = sub.add_parser("ask")
    p.add_argument("--domain", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--top-k", type=int, default=4)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("issue-build")
    p.add_argument("--date", required=True)
    p.add_argument("--kind", default="daily", choices=["daily", "weekly"])
    p.set_defaults(func=cmd_issue_build)

    p = sub.add_parser("issue-deliver")
    p.add_argument("--date", required=True)
    p.add_argument("--channel", default="inapp")
    p.set_defaults(func=cmd_issue_deliver)

    args = parser.parse_args(argv)
    init_db()
    try:
        return args.func(args)
    except UnknownDomain as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except (NoChunks, RetrieveError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
