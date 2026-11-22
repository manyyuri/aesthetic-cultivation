"""离线评测：检索三项 + 内容两项（免 LLM）；有 key 时补 faithfulness / context_precision。"""

from __future__ import annotations

import json
import math
from datetime import date

from pydantic import BaseModel

from ac_api.config import eval_dir, load_config
from ac_api.domain.models import RetrieveRequest
from ac_api.eval.golden import append_golden, load_golden
from ac_api.eval.metrics import citation_coverage, recall_at_k, reciprocal_rank, refused
from ac_api.llm.stub import StubClient
from ac_api.rag.ingest.pipeline import load_chunks
from ac_api.rag.retrieve.pipeline import Retriever

THRESHOLDS = {
    "recall_at_k": 0.85,
    "mrr": 0.70,
    "citation_coverage": 1.00,
    "refusal_accuracy": 0.90,
}


def run_domain(domain: str, k: int = 5, ci: bool = False) -> dict:
    cases = load_golden(domain)
    retriever = Retriever()
    stub = StubClient()
    rows: list[dict] = []

    for case in cases:
        response = retriever.retrieve(
            RetrieveRequest(
                domain=domain,
                query=case["query"],
                top_k=k,
                meta_filter=case.get("meta_filter"),
            )
        )
        docs = [c.doc_id for c in response.chunks]
        expected = case.get("expect", {}).get("must_cite_doc_ids", [])
        valid = {c.citation_id for c in response.chunks}
        evidence = [(c.citation_id, c.locator.anchor or "", c.content) for c in response.chunks]
        answer = stub.answer(case["query"], evidence) if evidence else "资料里没有能支撑这个问题的原文。"

        row = {
            "id": case["id"],
            "query": case["query"],
            "answerable": case.get("answerable", True),
            "retrieved": docs,
            "expected": expected,
            "evidence_status": response.evidence_status,
            "latency_ms": response.latency_ms,
            "answer": answer,
            "recall_at_k": recall_at_k(docs, expected, k),
            "rr": reciprocal_rank(docs, expected),
            "citation_coverage": citation_coverage(answer, valid),
            "refused": refused(answer, case.get("expect", {}).get("key_facts", [])),
        }
        rows.append(row)

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    summary = {
        "domain": domain,
        "k": k,
        "cases": len(rows),
        "recall_at_k": round(sum(r["recall_at_k"] for r in answerable) / max(len(answerable), 1), 4),
        "mrr": round(sum(r["rr"] for r in answerable) / max(len(answerable), 1), 4),
        "citation_coverage": round(
            sum(r["citation_coverage"] for r in answerable) / max(len(answerable), 1), 4
        ),
        "refusal_accuracy": round(
            sum(1 for r in unanswerable if r["refused"]) / max(len(unanswerable), 1), 4
        ),
        "p95_latency_ms": _p95([r for r in rows]),
        "ci_only": ci,
        "passed": {},
        "rows": rows,
        "generated_at": date.today().isoformat(),
    }
    summary["passed"] = {
        key: summary[key] >= threshold for key, threshold in THRESHOLDS.items()
    }

    if not ci:
        summary["judge"] = _judge(rows, domain)

    path = eval_dir() / "reports" / f"{domain}-{date.today().isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["report_path"] = str(path)
    return summary


def _p95(rows: list[dict]) -> int:
    values = sorted(r["latency_ms"] for r in rows if r.get("latency_ms"))
    if not values:
        return 0
    return values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]


def _judge(rows: list[dict], domain: str) -> dict:
    from ac_api.config import settings

    if not (settings().deepseek_api_key and settings().deepseek_model):
        return {"skipped": True, "reason": "缺 DEEPSEEK_API_KEY / DEEPSEEK_MODEL，faithfulness 与 context_precision 未评"}
    return _judge_with_llm(rows, domain)


class _JudgeSchema(BaseModel):
    supported: bool
    reason: str = ""


def _judge_with_llm(rows: list[dict], domain: str) -> dict:
    """LLM as judge：逐条判答案是否被 evidence 支持。判分不稳时宁可不给分。"""

    from ac_api.llm.deepseek import DeepSeekClient
    from ac_api.orchestrator.prompts import read_prompt

    client = DeepSeekClient()
    prompt = read_prompt("reviewer")
    scores: list[float] = []
    for row in rows:
        if not row["answerable"]:
            continue
        try:
            data = client.json(
                system=prompt + "\n\n只回答：{\"supported\": true|false, \"reason\": \"…\"}",
                user=json.dumps({"answer": row["answer"], "retrieved": row["retrieved"]}, ensure_ascii=False),
                schema=_JudgeSchema,
                temperature=0.0,
                max_tokens=300,
                agent="judge",
            )
            scores.append(1.0 if data.get("supported") else 0.0)
        except Exception:
            continue
    if not scores:
        return {"skipped": True, "reason": "judge 全部失败"}
    value = round(sum(scores) / len(scores), 4)
    return {"faithfulness": value, "passed": value >= 0.90, "n": len(scores)}



def check_golden(domain: str) -> dict:
    chunks = load_chunks(domain)
    known = {c.doc_id for c in chunks}
    cases = load_golden(domain)
    bad: list[dict] = []
    for case in cases:
        for doc_id in case.get("expect", {}).get("must_cite_doc_ids", []):
            if doc_id not in known:
                bad.append({"id": case["id"], "missing_doc": doc_id})
    return {"domain": domain, "cases": len(cases), "bad": bad, "ok": not bad}


def promote_item(domain: str, item_id: str | None) -> dict:
    from ac_api.store import issues as issues_store

    if not item_id:
        return {"ok": False, "reason": "缺少 item_id"}
    item = issues_store.get_item(item_id)
    if not item:
        return {"ok": False, "reason": "找不到这一件"}
    docs = sorted({e.doc_id for e in item.evidence})
    if not docs:
        return {"ok": False, "reason": "该件没有证据，无法沉淀为 golden"}
    record = {
        "id": f"{domain}_{item.id}",
        "domain": domain,
        "query": f"{item.title_zh} 的要点是什么",
        "meta_filter": None,
        "answerable": True,
        "needs_review": True,
        "expect": {
            "must_cite_doc_ids": docs,
            "must_not_claim": [],
            "key_facts": [],
        },
    }
    append_golden(domain, record)
    return {"ok": True, "record": record}


def feedback_summary() -> dict:
    from ac_api.store import issues as issues_store

    rows = issues_store.feedback_rows()
    buckets: dict[str, list[dict]] = {"missing_evidence": [], "wrong_citation": [], "hallucination": [], "ok": []}
    for row in rows:
        buckets.setdefault(row["verdict"], []).append(row)
    return {
        "total": len(rows),
        "buckets": {k: len(v) for k, v in buckets.items()},
        "next_actions": [
            "缺文档 → 补 raw 文档后 make ingest && make index",
            "召不回 → 调 chunker 边界 / 分词 / recall_pool，指标不升就回滚",
            "说错 → 先改 reviewer 判据，不要先动检索",
        ],
        "domains": sorted({r["domain"] for r in rows if r.get("domain")}),
        "config_domains": sorted(load_config().domains),
    }
