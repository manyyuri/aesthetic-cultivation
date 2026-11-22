from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ac_api.api.schemas import DoneRequest
from ac_api.domain.models import Issue
from ac_api.store import issues as issues_store
from ac_api.store.db import connect

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("/today")
def today(kind: str = Query(default="daily", pattern="^(daily|weekly)$")):
    latest = issues_store.list_issues(limit=1)
    from datetime import date

    issue = issues_store.get_issue_by_date(date.today().isoformat(), kind)
    if not issue:
        return JSONResponse(
            status_code=202,
            content={
                "status": "building",
                "date": date.today().isoformat(),
                "kind": kind,
                "last_issue": latest[0].id if latest else None,
                "message": "今天的节目单正在排，通常 07:30 前就绪。",
            },
        )
    return issue


@router.get("")
def list_issues(limit: int = 20, offset: int = 0) -> list[Issue]:
    return issues_store.list_issues(limit=limit, offset=offset)


@router.get("/{issue_id}")
def get_issue(issue_id: str) -> Issue:
    issue = issues_store.get_issue_by_date(issue_id) if len(issue_id) == 10 else None
    if not issue:
        with connect() as conn:
            issue = issues_store.get_issue(conn, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="没有这一期")
    return issue


@router.post("/{issue_id}/items/{ordinal}/done")
def mark_done(issue_id: str, ordinal: int, body: DoneRequest) -> dict:
    with connect() as conn:
        issue = issues_store.get_issue(conn, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="没有这一期")
    item = next((i for i in issue.items if i.ord == ordinal), None)
    if not item:
        raise HTTPException(status_code=404, detail="没有这一件")
    issue_id, done_count, streak = issues_store.mark_item_done(item.id, body.done)
    return {"issue_id": issue_id, "done_count": done_count, "total": len(issue.items), "streak": streak}
