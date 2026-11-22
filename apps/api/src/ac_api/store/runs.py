"""run / step 落库：trace 时间线与 SSE 重放都靠它。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from ac_api.store.db import connect


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def start_run(kind: str, subject_id: str | None = None, budget: dict | None = None) -> str:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, kind, subject_id, status, started_at, budget_json, usage_json)"
            " VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (run_id, kind, subject_id, _now(), json.dumps(budget or {}), json.dumps({"prompt": 0, "completion": 0})),
        )
    return run_id


def log_step(
    run_id: str,
    seq: int,
    step: str,
    status: str = "ok",
    latency_ms: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    payload: dict[str, Any] | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO steps (run_id, seq, step, status, latency_ms, tokens_in, tokens_out, payload_json, ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                seq,
                step,
                status,
                latency_ms,
                tokens_in,
                tokens_out,
                json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
                _now(),
            ),
        )
        row = conn.execute("SELECT usage_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row:
            usage = json.loads(row["usage_json"] or "{}")
            usage["prompt"] = int(usage.get("prompt", 0)) + tokens_in
            usage["completion"] = int(usage.get("completion", 0)) + tokens_out
            conn.execute("UPDATE runs SET usage_json = ? WHERE id = ?", (json.dumps(usage), run_id))


def finish_run(run_id: str, status: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, ended_at = ?, error = ? WHERE id = ?",
            (status, _now(), error, run_id),
        )


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        steps = conn.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
    return {
        "run": {
            **dict(row),
            "budget": json.loads(row["budget_json"] or "{}"),
            "usage": json.loads(row["usage_json"] or "{}"),
        },
        "steps": [
            {
                **dict(step),
                "payload": json.loads(step["payload_json"]) if step["payload_json"] else None,
            }
            for step in steps
        ],
    }


def list_runs(kind: str | None = None, limit: int = 20) -> list[dict]:
    with connect() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM runs WHERE kind = ? ORDER BY started_at DESC LIMIT ?", (kind, limit)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
