"""编排内核：建期 / 推送 / 追问。只依赖 port 层（rag、llm、store、push），便于将来换语言。"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from ac_api.config import load_config, settings
from ac_api.curation.compose import compose_issue
from ac_api.domain.models import Issue, RetrieveRequest
from ac_api.llm.answer import answer_question
from ac_api.llm.grounding import has_any_citation, precheck, uncited_fact_sentences
from ac_api.llm.stub import get_client
from ac_api.obs.logger import get_logger
from ac_api.obs.metrics import metrics
from ac_api.obs.trace import Tracer
from ac_api.push import DeliveryReport, deliver
from ac_api.rag.retrieve.pipeline import Retriever
from ac_api.store import issues as issues_store
from ac_api.store import runs as runs_store

log = get_logger("orchestrator")
CITE_RE = re.compile(r"\[(S\d+)\]")


def build_issue(publish_date: str, kind: str = "daily") -> Issue:
    existing = issues_store.get_issue_by_date(publish_date, kind)
    if existing and existing.status == "delivered":
        raise issues_store.AlreadyDelivered(existing.id)
    run_id = runs_store.start_run("issue_build", f"i_{publish_date}")
    tracer = Tracer(run_id)
    started = time.monotonic()
    tracer.event("run.started", run_id=run_id, kind="issue_build", subject_id=f"i_{publish_date}")
    try:
        issue = compose_issue(publish_date, kind, tracer)
        if existing:
            issue = issue.model_copy(update={"issue_no": existing.issue_no})
        issues_store.save_issue(issue)
        saved = issues_store.get_issue_by_id(issue.id) or issue
        runs_store.finish_run(run_id, "ok")
        metrics.inc("issue_build_total", {"status": saved.status})
        metrics.observe(
            "issue_build_duration_seconds",
            time.monotonic() - started,
            {"kind": kind},
        )
        metrics.gauge("issue_fill_rate", len(saved.items) / max(len(saved.items) or 3, 3))
        tracer.event("run.finished", status=saved.status, issue_id=saved.id)
        return saved
    except Exception as exc:
        runs_store.finish_run(run_id, "failed", str(exc)[:400])
        metrics.inc("issue_build_total", {"status": "failed"})
        log.info("issue_build_failed", extra={"data": {"error": str(exc)[:300]}})
        raise


def deliver_issue(publish_date: str, channels: list[str] | None = None) -> DeliveryReport:
    issue = issues_store.get_issue_by_date(publish_date)
    if not issue:
        raise ValueError(f"{publish_date} 还没有排期，先跑 make issue:build")
    if issue.status not in ("ready", "partial"):
        raise ValueError(f"该期状态为 {issue.status}，不推送草稿")
    channels = channels or ["inapp"]
    report = deliver(issue, channels)
    for result in report.results:
        metrics.inc(
            "push_delivery_total",
            {"channel": result.get("channel", "?"), "status": "ok" if result.get("ok") else "fail"},
        )
    if report.delivered:
        issues_store.mark_delivered(issue.id)
    return report


# ---------------- 追问 ----------------

async def ask_stream(run_id: str, item_id: str, question: str) -> AsyncIterator[dict]:
    item = issues_store.get_item(item_id)
    if not item:
        yield {"seq": 1, "type": "run.error", "code": "item_not_found", "message": item_id, "retryable": False}
        return

    events: list[dict] = []
    tracer = Tracer(run_id, emit=events.append)
    tracer.event("run.started", run_id=run_id, kind="ask", subject_id=item_id)
    for event in _drain(events):
        yield event

    started = time.monotonic()
    with _timer() as elapsed:
        response = await asyncio.to_thread(
            Retriever().retrieve,
            RetrieveRequest(domain=item.domain, query=question, top_k=4),
        )
    tracer.step(
        "retrieve",
        latency_ms=elapsed(),
        summary=f"{response.evidence_status} · {len(response.chunks)} 条",
        payload={"query": question, "status": response.evidence_status},
    )
    tracer.event(
        "retrieval.result",
        attempt=1,
        req={"domain": item.domain, "query": question, "top_k": 4},
        res=response.model_dump(mode="json"),
    )
    for event in _drain(events):
        yield event

    refusal = precheck(question, [c.content for c in response.chunks])
    if response.evidence_status == "insufficient" or not response.chunks or refusal:
        answer = "资料里没有能支撑这个问题的原文。"
        if response.missing_hint:
            answer += f"（{response.missing_hint}）"
        elif refusal and refusal.startswith("year_not_in_evidence:"):
            answer += f"（资料里没有 {refusal.split(':', 1)[1]} 年的记录）"
        tracer.step("answer", ok=True, summary="拒答 · 证据不足")
        tracer.event("run.finished", status="refused", answer_md=answer)
        for event in _drain(events):
            yield event
        runs_store.finish_run(run_id, "refused")
        metrics.inc("run_total", {"status": "refused"})
        return

    evidence = [
        (c.citation_id, f"{c.locator.doc_title} · {c.locator.anchor or ''}".strip(" ·"), c.content)
        for c in response.chunks
    ]
    client = get_client()
    with _timer() as elapsed:
        try:
            answer = await asyncio.to_thread(answer_question, question, evidence, client, run_id=run_id)
        except Exception as exc:  # 余额/网络/结构化失败：退回抽取式，别让 run 卡在 running
            from ac_api.llm.stub import StubClient

            log.info("answer_llm_fallback", extra={"data": {"error": str(exc)[:160]}})
            tracer.step("answer.fallback", ok=True, summary=f"模型不可用：{str(exc)[:60]}")
            answer = await asyncio.to_thread(answer_question, question, evidence, StubClient())
    tracer.step("answer", latency_ms=elapsed(), summary=answer[:60])
    tracer.event("llm.delta", step="answer", text=answer)
    for event in _drain(events):
        yield event

    valid = {c.citation_id for c in response.chunks}
    if not has_any_citation(answer, valid):
        # 一句都没引用 ⇒ 等于没有证据支撑，按拒答处理
        tracer.step("review", ok=False, summary="no_citation")
        tracer.event("review.verdict", verdict="REFUSE", issues=[], loop=1)
        tracer.event("run.finished", status="refused", answer_md="资料里没有能支撑这个问题的原文。")
        for event in _drain(events):
            yield event
        runs_store.finish_run(run_id, "refused")
        metrics.inc("run_total", {"status": "refused"})
        return
    for sentence in uncited_fact_sentences(answer, valid):
        tracer.event("claim.checked", sentence=sentence, citations=[], verdict="unsupported")
    checked = 0
    for sentence in re.split(r"(?<=[。！？\n])", answer):
        if not sentence.strip():
            continue
        cites = CITE_RE.findall(sentence)
        ok = bool(cites) and all(c in valid for c in cites)
        checked += 1
        tracer.event("claim.checked", sentence=sentence.strip()[:120], citations=cites, verdict="ok" if ok else "unsupported")
    for event in _drain(events):
        yield event

    verdict = "PASS" if checked else "REFUSE"
    tracer.event("review.verdict", verdict=verdict, issues=[], loop=1)
    tracer.event("run.finished", status="answered", answer_md=answer)
    for event in _drain(events):
        yield event
    runs_store.finish_run(run_id, "ok")
    metrics.inc("run_total", {"status": "answered"})
    metrics.observe("run_duration_seconds", time.monotonic() - started, {"status": "answered"})


def _drain(events: list[dict]) -> list[dict]:
    out = list(events)
    events.clear()
    return out


class _timer:
    def __enter__(self):
        self._t0 = time.monotonic()
        return lambda: int((time.monotonic() - self._t0) * 1000)

    def __exit__(self, *exc):
        return False


def start_ask(item_id: str, question: str) -> str:
    run_id = runs_store.start_run("ask", item_id, budget={"max_retrieve_calls": 3})
    return run_id


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


__all__ = ["build_issue", "deliver_issue", "ask_stream", "start_ask", "settings", "load_config"]
