from __future__ import annotations

import argparse
import json

from ac_api.eval.runner import check_golden, feedback_summary, run_domain


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ac-eval")
    parser.add_argument("--domain", default="ballet")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--feedback", action="store_true")
    args = parser.parse_args(argv)

    if args.check:
        result = check_golden(args.domain)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.feedback:
        print(json.dumps(feedback_summary(), ensure_ascii=False, indent=2))
        return 0

    report = run_domain(args.domain, args.k, args.ci)
    rows = report.pop("rows")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    for row in rows:
        flag = "ok " if row["recall_at_k"] else "MISS"
        print(f"  {flag} {row['id']:<16} status={row['evidence_status']:<12} docs={row['retrieved'][:2]}")
    return 0 if all(report["passed"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
