"""min_score 校准：在 golden 上扫阈值，输出"召回不掉太多前提下拒答最准"的点。

用法：
  python scripts/calibrate.py --domain art --k 5
  python scripts/calibrate.py --domain ballet --grid 0.05,0.20,0.35,0.50
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ac_api.config import eval_dir, load_config  # noqa: E402
from ac_api.domain.models import RetrieveRequest  # noqa: E402
from ac_api.eval.golden import load_golden  # noqa: E402
from ac_api.eval.metrics import recall_at_k, reciprocal_rank, refused  # noqa: E402
from ac_api.llm.stub import REFUSAL, StubClient  # noqa: E402
from ac_api.rag.index.embedding import get_embedder  # noqa: E402
from ac_api.rag.retrieve.pipeline import Retriever  # noqa: E402
from ac_api.rag.retrieve.rerank import get_reranker  # noqa: E402


def scan(domain: str, k: int, grid: list[float]) -> dict:
    from ac_api.eval.runner import warmup

    cases = load_golden(domain)
    warmup()
    retriever = Retriever()
    stub = StubClient()
    rows: list[dict] = []
    for threshold in grid:
        answered = 0
        recalls: list[float] = []
        rrs: list[float] = []
        refusals: list[bool] = []
        for case in cases:
            response = retriever.retrieve(
                RetrieveRequest(
                    domain=domain,
                    query=case["query"],
                    top_k=k,
                    meta_filter=case.get("meta_filter"),
                    options={"min_score": threshold},
                )
            )
            docs = [c.doc_id for c in response.chunks]
            expected = case.get("expect", {}).get("must_cite_doc_ids", [])
            evidence = [(c.citation_id, c.locator.anchor or "", c.content) for c in response.chunks]
            answer = stub.answer(case["query"], evidence) if evidence else REFUSAL
            if case.get("answerable", True):
                recalls.append(recall_at_k(docs, expected, k))
                rrs.append(reciprocal_rank(docs, expected))
                answered += 1 if answer and not answer.startswith("资料里没有") else 0
            else:
                refusals.append(refused(answer, case.get("expect", {}).get("key_facts", [])))
        rows.append(
            {
                "min_score": round(threshold, 3),
                "recall_at_k": round(sum(recalls) / max(len(recalls), 1), 4),
                "mrr": round(sum(rrs) / max(len(rrs), 1), 4),
                "refusal_accuracy": round(sum(refusals) / max(len(refusals), 1), 4),
                "answered": answered,
            }
        )
    return {
        "domain": domain,
        "k": k,
        "embedder": get_embedder().fingerprint,
        "reranker": get_reranker().signature,
        "generated_at": date.today().isoformat(),
        "rows": rows,
    }


def pick(rows: list[dict], max_recall_drop: float = 0.03) -> dict:
    best = max(row["recall_at_k"] for row in rows)
    eligible = [row for row in rows if row["recall_at_k"] >= best - max_recall_drop]
    return max(eligible, key=lambda row: (row["refusal_accuracy"], row["min_score"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="art")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--grid", default=None, help="逗号分隔；默认 0.05~0.60 步长 0.05")
    args = parser.parse_args()

    grid = (
        [float(x) for x in args.grid.split(",")]
        if args.grid
        else [round(0.05 * i, 2) for i in range(1, 13)]
    )
    report = scan(args.domain, args.k, grid)
    chosen = pick(report["rows"])
    report["chosen"] = chosen
    path = eval_dir() / "reports" / f"calibration-{args.domain}-{report['generated_at']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"== {args.domain} · k={args.k} · {report['embedder']} · rerank={report['reranker']}")
    print(f"{'min_score':>10} {'recall@k':>9} {'mrr':>7} {'refusal':>8} {'answered':>9}")
    for row in report["rows"]:
        print(
            f"{row['min_score']:>10.2f} {row['recall_at_k']:>9.3f} {row['mrr']:>7.3f} "
            f"{row['refusal_accuracy']:>8.3f} {row['answered']:>9}"
        )
    print(f"\n建议 min_score = {chosen['min_score']}（recall 掉幅 ≤3% 前提下拒答最准）")
    print(f"报告：{path}")
    config = load_config()
    print(
        f"当前 config 里 rerank={report['reranker']} 的阈值 = {config.min_score_for(report['reranker'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
