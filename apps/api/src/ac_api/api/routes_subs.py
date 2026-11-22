from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from ac_api.api.deps import require_key
from ac_api.api.schemas import SubscribeUpdate
from ac_api.store.db import connect

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("")
def get_subscription() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM subscriptions LIMIT 1").fetchone()
    if not row:
        return {
            "id": None,
            "kind": "daily",
            "time_of_day": "07:30",
            "channels": ["inapp"],
            "active": True,
            "streak": 0,
            "last_done_date": None,
        }
    return {
        "id": row["id"],
        "kind": row["kind"],
        "time_of_day": row["time_of_day"],
        "channels": json.loads(row["channels_json"]),
        "active": bool(row["active"]),
        "streak": row["streak"],
        "last_done_date": row["last_done_date"],
    }


@router.put("", dependencies=[Depends(require_key)])
def put_subscription(body: SubscribeUpdate) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT id FROM subscriptions LIMIT 1").fetchone()
        if row:
            conn.execute(
                "UPDATE subscriptions SET kind = ?, time_of_day = ?, channels_json = ?, active = ? WHERE id = ?",
                (body.kind, body.time_of_day, json.dumps(body.channels), int(body.active), row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO subscriptions (id, kind, time_of_day, channels_json, active, streak)"
                " VALUES ('s_local', ?, ?, ?, ?, 0)",
                (body.kind, body.time_of_day, json.dumps(body.channels), int(body.active)),
            )
    return get_subscription()


@router.post("/test", dependencies=[Depends(require_key)])
def test_push() -> dict:
    from datetime import date

    from ac_api.orchestrator.core import deliver_issue
    from ac_api.store import issues as issues_store

    issue = issues_store.get_issue_by_date(date.today().isoformat())
    if not issue:
        return {"ok": False, "reason": "今天还没有已生成的期，先跑 make issue:build"}
    report = deliver_issue(issue.publish_date, ["email"])
    return report.model_dump()
