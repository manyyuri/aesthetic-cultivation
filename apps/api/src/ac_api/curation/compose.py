"""组期：选题 → 检索 → 挑件 → 锚点 → 写作 → 评审 → 降级 → 组装。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from ac_api.config import load_config
from ac_api.curation.anchors import build_anchor
from ac_api.curation.candidates import Candidate, build_candidates
from ac_api.curation.review import review
from ac_api.curation.write import get_writer
from ac_api.domain.models import (
    Anchor,
    Chunk,
    Evidence,
    Issue,
    Item,
    Locator,
    RetrieveRequest,
    RetrievedChunk,
)
from ac_api.obs.logger import get_logger
from ac_api.obs.trace import Timer, Tracer
from ac_api.rag.retrieve.pipeline import Retriever
from ac_api.store import issues as issues_store

log = get_logger("compose")


def _to_chunk(rc: RetrievedChunk) -> Chunk:
    return Chunk(
        chunk_id=rc.chunk_id,
        doc_id=rc.doc_id,
        domain=rc.domain,
        text=rc.content,
        locator=Locator.model_validate(rc.locator.model_dump()),
        metadata=dict(rc.metadata),
        source_priority=rc.source_priority,
    )


def _marks(ordinal: int, count: int) -> list[str]:
    marks = [f"№{ordinal:03d}"]
    for i in range(1, count):
        marks.append(f"№{ordinal:03d}·{chr(96 + i)}")
    return marks


def _evidence(ordinal: int, retrieved: list[RetrievedChunk]) -> list[Evidence]:
    marks = _marks(ordinal, len(retrieved))
    return [
        Evidence(
            mark=marks[i],
            chunk_id=rc.chunk_id,
            doc_id=rc.doc_id,
            source=rc.source,
            excerpt=rc.content[:220],
            scores={k: float(v) for k, v in rc.scores.items()},
        )
        for i, rc in enumerate(retrieved)
    ]


def _pick_item(
    candidate: Candidate,
    ordinal: int,
    issue_id: str,
    tracer: Tracer,
    retriever: Retriever,
) -> tuple[Item | None, str]:
    cfg = load_config().curation
    spec = load_config().domain(candidate.domain)
    query = " ".join(x for x in (candidate.title_zh, candidate.title_orig, candidate.heading) if x)

    with Timer() as timer:
        try:
            response = retriever.retrieve(
                RetrieveRequest(domain=candidate.domain, query=query, top_k=3)
            )
        except Exception as exc:
            tracer.step("retrieve", ok=False, summary=str(exc)[:80], payload={"query": query})
            return None, "retrieve_error"
    tracer.step(
        "retrieve",
        latency_ms=timer.ms,
        summary=f"{response.evidence_status} · {len(response.chunks)} 条",
        payload={"query": query, "status": response.evidence_status, "doc_ids": [c.doc_id for c in response.chunks]},
    )
    tracer.event(
        "retrieval.result",
        attempt=1,
        req={"domain": candidate.domain, "query": query, "top_k": 3},
        res=response.model_dump(mode="json"),
    )

    if response.evidence_status != "found" or not response.chunks:
        return None, "evidence_insufficient"
    if candidate.doc_id not in {c.doc_id for c in response.chunks}:
        return None, "evidence_other_doc"

    chunks = [_to_chunk(rc) for rc in response.chunks if rc.doc_id == candidate.doc_id]
    anchor = build_anchor(candidate.domain, candidate.chunks, candidate.metadata)
    if not anchor:
        tracer.step("anchor", ok=False, summary="锚点校验失败", payload={"doc_id": candidate.doc_id})
        return None, "anchor_invalid"

    writer = get_writer()
    with Timer() as timer:
        written = writer.write(candidate, chunks, anchor)
    tracer.step("write", latency_ms=timer.ms, summary=written.hook[:40], payload=written.model_dump(mode="json"))

    verdict = review(
        written,
        candidate,
        chunks,
        spec,
        hook_max_chars=int(cfg.get("daily", {}).get("hook_max_chars", 60)),
    )
    tracer.step(
        "review",
        ok=verdict.verdict == "PASS",
        summary=verdict.verdict,
        payload=verdict.model_dump(mode="json"),
    )
    if verdict.verdict != "PASS":
        tracer.event(
            "review.verdict",
            verdict=verdict.verdict,
            issues=[i.model_dump() for i in verdict.issues],
            loop=verdict.loop,
        )
        return None, f"review_{verdict.verdict.lower()}"

    used = [rc for rc in response.chunks if rc.doc_id == candidate.doc_id][:2]
    return (
        Item(
            id=f"it_{issue_id}_{ordinal:02d}",
            issue_id=issue_id,
            ord=ordinal,
            domain=candidate.domain,
            title_zh=written.title_zh,
            title_orig=written.title_orig,
            meta_lines=written.meta_lines,
            hook=written.hook,
            anchor=Anchor.model_validate(written.anchor.model_dump()),
            evidence=_evidence(ordinal, used),
            image_url=candidate.metadata.get("image_url"),
            rank_score=candidate.rank_score,
        ),
        "ok",
    )


def compose_issue(publish_date: str, kind: str = "daily", tracer: Tracer | None = None) -> Issue:
    cfg = load_config().curation
    plan = cfg.get(kind, cfg.get("daily", {}))
    rules = cfg.get("rules", {})
    mix: list[str] = list(plan.get("domain_mix", ["art", "music", "ballet"]))
    target_items = int(plan.get("items", len(mix)))
    issue_id = f"i_{publish_date}" + ("" if kind == "daily" else f"_{kind}")

    if tracer is None:
        from ac_api.store.runs import start_run

        tracer = Tracer(start_run("issue_build", issue_id))

    used_docs = issues_store.recent_doc_ids(int(rules.get("no_repeat_within_days", 90)))
    used_keys = issues_store.recent_item_keys(int(rules.get("no_repeat_item_days", rules.get("no_repeat_within_days", 90))))
    retriever = Retriever()

    pool: dict[str, list[Candidate]] = {}
    with Timer() as timer:
        for domain in sorted(set(mix)):
            pool[domain] = build_candidates(
                domain,
                publish_date,
                limit=int(rules.get("max_candidates", 24)) // max(len(set(mix)), 1),
                used_docs=used_docs,
                used_keys=used_keys,
                no_repeat_doc_days=int(rules.get("no_repeat_doc_within_days", 14)),
            )
    tracer.step(
        "candidates",
        latency_ms=timer.ms,
        summary=" ".join(f"{d}:{len(v)}" for d, v in pool.items()),
        payload={"counts": {d: len(v) for d, v in pool.items()}, "date": publish_date},
    )

    items: list[Item] = []
    rejected: list[dict] = []
    for domain in mix:
        if len(items) >= target_items:
            break
        for candidate in pool.get(domain, []):
            ordinal = len(items) + 1
            item, reason = _pick_item(candidate, ordinal, issue_id, tracer, retriever)
            if item:
                items.append(item)
                tracer.event(
                    "candidate.picked",
                    ord=ordinal,
                    item_id=item.id,
                    domain=domain,
                    rank_score=candidate.rank_score,
                )
                break
            rejected.append({"doc_id": candidate.doc_id, "reason": reason})
            tracer.event("candidate.rejected", item_id=candidate.doc_id, reason=reason)

    status = "ready" if len(items) >= target_items else "partial"
    if len(items) < 2:
        items = _revisit_items(issue_id, items, tracer)
        status = "partial" if items else "draft"

    titles = [i.title_zh for i in items]
    if kind == "weekly":
        title = "本周节目单"
    else:
        title = {3: "今夜三幕", 2: "今夜两幕", 1: "今夜一幕"}.get(len(items), "今夜三幕")
    subtitle = "、".join(titles) if titles else "今天的资料还没排够，明天再来。"
    if items and len(items) < 3 and kind == "daily":
        subtitle = "资料不足，本期只排了 " + subtitle

    issue = Issue(
        id=issue_id,
        kind=kind,  # type: ignore[arg-type]
        issue_no=0,
        publish_date=publish_date,
        title=title,
        subtitle=subtitle,
        minutes=int(plan.get("minute_budget", 20)),
        status=status,  # type: ignore[arg-type]
        generated_at=datetime.now(UTC),
        items=items,
    )
    tracer.step(
        "assemble",
        ok=status in ("ready", "partial"),
        summary=f"{status} · {len(items)}/{target_items} 件 · rejected={len(rejected)}",
        payload={"status": status, "items": [i.id for i in items], "rejected": rejected},
    )
    log.info("issue_composed", extra={"issue_id": issue_id, "data": {"status": status, "items": len(items)}})
    return issue


def _revisit_items(issue_id: str, current: list[Item], tracer: Tracer) -> list[Item]:
    """降级：素材不足时改发往期回访（把旧件搬进本期，不改内容）。"""
    out = list(current)
    if out:
        out[0] = out[0].model_copy(update={"hook": "回访 · " + out[0].hook})
    for previous in issues_store.list_issues(limit=2):
        for item in previous.items:
            if len(out) >= 2:
                break
            ordinal = len(out) + 1
            clone = item.model_copy(
                update={
                    "id": f"it_{issue_id}_{ordinal:02d}",
                    "issue_id": issue_id,
                    "ord": ordinal,
                    "done_at": None,
                    "hook": item.hook if item.hook.startswith("回访") else "回访 · " + item.hook,
                }
            )
            out.append(clone)
    if out and len(out) < 2:
        tracer.event("issue.degrade", reason="insufficient_material", items=len(out))
    return out
