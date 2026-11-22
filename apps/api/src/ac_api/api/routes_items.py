from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from ac_api.api.schemas import AskRequest, HitlRequest
from ac_api.api.sse import format_sse, hub
from ac_api.domain.models import Item
from ac_api.orchestrator.core import ask_stream, start_ask
from ac_api.store import issues as issues_store
from ac_api.store import runs as runs_store

router = APIRouter(tags=["items"])


@router.get("/api/items/{item_id}")
def get_item(item_id: str) -> Item:
    item = issues_store.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="没有这一件")
    return item


@router.post("/api/items/{item_id}/ask")
async def ask(item_id: str, body: AskRequest) -> dict:
    if not issues_store.get_item(item_id):
        raise HTTPException(status_code=404, detail="没有这一件")
    run_id = start_ask(item_id, body.question)

    async def runner() -> None:
        try:
            async for event in ask_stream(run_id, item_id, body.question):
                hub.publish(run_id, event)
        except Exception as exc:  # 事件流里也要有终止事件
            runs_store.finish_run(run_id, "failed", str(exc)[:300])
            hub.publish(
                run_id,
                {
                    "seq": 9999,
                    "type": "run.error",
                    "code": "ask_failed",
                    "message": str(exc)[:300],
                    "retryable": True,
                },
            )

    hub.spawn(run_id, runner())
    return {"run_id": run_id, "stream": f"/api/runs/{run_id}/stream"}


@router.get("/api/runs")
def list_runs(kind: str | None = None, limit: int = 20) -> list[dict]:
    return runs_store.list_runs(kind=kind, limit=limit)


@router.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    data = runs_store.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="没有这个 run")
    return data


def _replay(run_id: str) -> list[dict]:
    data = runs_store.get_run(run_id)
    if not data:
        return []
    events: list[dict] = []
    for step in data["steps"]:
        events.append(
            {
                "seq": step["seq"],
                "ts": step["ts"],
                "type": "step.finished",
                "step": step["step"],
                "ok": step["status"] == "ok",
                "latency_ms": step["latency_ms"],
                "summary": "",
                "payload": step["payload"],
            }
        )
    events.append(
        {
            "seq": (events[-1]["seq"] + 1) if events else 1,
            "type": "run.finished",
            "status": {"ok": "answered", "refused": "refused"}.get(
                data["run"]["status"], data["run"]["status"]
            ),
        }
    )
    return events


@router.get("/api/runs/{run_id}/stream")
async def stream(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    data = runs_store.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="没有这个 run")

    async def generator():
        if data["run"]["status"] != "running":
            for event in _replay(run_id):
                yield format_sse(event)
            yield "event: end\ndata: {}\n\n"
            return

        queue = hub.subscribe(run_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield format_sse(event)
                if event.get("type") in ("run.finished", "run.error"):
                    break
            yield "event: end\ndata: {}\n\n"
        finally:
            hub.unsubscribe(run_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/api/runs/{run_id}/hitl")
def hitl(run_id: str, body: HitlRequest) -> dict:
    data = runs_store.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="没有这个 run")
    runs_store.log_step(run_id, 9001, "hitl", status="ok", payload=body.model_dump())
    runs_store.finish_run(run_id, "ok" if body.decision == "approve" else "rejected")
    return {"run_id": run_id, "decision": body.decision}
