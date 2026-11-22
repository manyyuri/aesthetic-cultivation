"""期/件的读写。一期 = 一条 issues + n 条 items。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

from ac_api.domain.models import Anchor, Evidence, Issue, Item, MetaLine
from ac_api.store.db import connect


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def next_issue_no(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(issue_no), 0) AS n FROM issues").fetchone()
    return int(row["n"]) + 1


def _row_to_item(row) -> Item:
    return Item(
        id=row["id"],
        issue_id=row["issue_id"],
        ord=int(row["ord"]),
        domain=row["domain"],
        title_zh=row["title_zh"],
        title_orig=row["title_orig"],
        meta_lines=[MetaLine(**m) for m in json.loads(row["meta_json"] or "[]")],
        hook=row["hook"],
        anchor=Anchor.model_validate_json(row["anchor_json"]),
        evidence=[Evidence(**e) for e in json.loads(row["evidence_json"] or "[]")],
        image_url=row["image_url"],
        done_at=datetime.fromisoformat(row["done_at"]) if row["done_at"] else None,
        rank_score=float(row["rank_score"] or 0),
    )


def get_issue_by_id(issue_id: str) -> Issue | None:
    with connect() as conn:
        return get_issue(conn, issue_id)


def get_issue(conn, issue_id: str) -> Issue | None:
    row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    if not row:
        return None
    items = conn.execute("SELECT * FROM items WHERE issue_id = ? ORDER BY ord", (issue_id,)).fetchall()
    return Issue(
        id=row["id"],
        kind=row["kind"],
        issue_no=int(row["issue_no"]),
        publish_date=row["publish_date"],
        title=row["title"],
        subtitle=row["subtitle"],
        minutes=int(row["minutes"]),
        status=row["status"],
        generated_at=datetime.fromisoformat(row["generated_at"]) if row["generated_at"] else None,
        delivered_at=datetime.fromisoformat(row["delivered_at"]) if row["delivered_at"] else None,
        items=[_row_to_item(i) for i in items],
    )


def get_issue_by_date(date_str: str, kind: str = "daily") -> Issue | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM issues WHERE publish_date = ? AND kind = ?", (date_str, kind)
        ).fetchone()
        return get_issue(conn, row["id"]) if row else None


def list_issues(limit: int = 20, offset: int = 0) -> list[Issue]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM issues ORDER BY publish_date DESC, issue_no DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [issue for row in rows if (issue := get_issue(conn, row["id"]))]


def save_issue(issue: Issue, *, replace_items: bool = True) -> None:
    with connect() as conn:
        conn.execute("BEGIN")
        try:
            exists = conn.execute("SELECT status, issue_no FROM issues WHERE id = ?", (issue.id,)).fetchone()
            if exists and exists["status"] == "delivered":
                raise AlreadyDelivered(issue.id)
            no = exists["issue_no"] if exists else next_issue_no(conn)
            conn.execute(
                """
                INSERT INTO issues (id, kind, issue_no, publish_date, title, subtitle, minutes,
                                    status, generated_at, delivered_at, cover_json, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  title = excluded.title, subtitle = excluded.subtitle, minutes = excluded.minutes,
                  status = excluded.status, generated_at = excluded.generated_at
                """,
                (
                    issue.id,
                    issue.kind,
                    no,
                    issue.publish_date,
                    issue.title,
                    issue.subtitle,
                    issue.minutes,
                    issue.status,
                    issue.generated_at.isoformat() if issue.generated_at else _now(),
                    issue.delivered_at.isoformat() if issue.delivered_at else None,
                    json.dumps({"accent": issue.items[0].domain if issue.items else "art"}),
                    None,
                ),
            )
            if replace_items:
                conn.execute("DELETE FROM items WHERE issue_id = ?", (issue.id,))
            for item in issue.items:
                conn.execute(
                    """
                    INSERT INTO items (id, issue_id, ord, domain, title_zh, title_orig, meta_json,
                                       hook, anchor_json, evidence_json, image_url, done_at, rank_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        issue.id,
                        item.ord,
                        item.domain,
                        item.title_zh,
                        item.title_orig,
                        json.dumps([m.model_dump() for m in item.meta_lines], ensure_ascii=False),
                        item.hook,
                        item.anchor.model_dump_json(),
                        json.dumps([e.model_dump() for e in item.evidence], ensure_ascii=False),
                        item.image_url,
                        item.done_at.isoformat() if item.done_at else None,
                        item.rank_score,
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


class AlreadyDelivered(Exception):
    def __init__(self, issue_id: str) -> None:
        super().__init__(f"该期已推送，不允许覆盖：{issue_id}")


def mark_delivered(issue_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE issues SET status = 'delivered', delivered_at = ? WHERE id = ?", (_now(), issue_id)
        )


def get_item(item_id: str) -> Item | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _row_to_item(row) if row else None


def mark_item_done(item_id: str, done: bool) -> tuple[str, int, int]:
    with connect() as conn:
        row = conn.execute("SELECT issue_id FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise KeyError(item_id)
        issue_id = row["issue_id"]
        conn.execute(
            "UPDATE items SET done_at = ? WHERE id = ?",
            (_now() if done else None, item_id),
        )
        issue_row = conn.execute(
            "SELECT publish_date FROM issues WHERE id = ?", (issue_id,)
        ).fetchone()
        counts = conn.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN done_at IS NOT NULL THEN 1 ELSE 0 END) AS done "
            "FROM items WHERE issue_id = ?",
            (issue_id,),
        ).fetchone()
        done_count = int(counts["done"] or 0)
        total = int(counts["total"] or 0)
        streak = 0
        if done and done_count >= total and total:
            streak = _bump_streak(conn, issue_row["publish_date"])
        else:
            streak = _current_streak(conn)
        return issue_id, done_count, streak


def _bump_streak(conn, day: str) -> int:
    row = conn.execute("SELECT id, streak, last_done_date FROM subscriptions LIMIT 1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO subscriptions (id, kind, time_of_day, channels_json, active, streak, last_done_date)"
            " VALUES (?, 'daily', '07:30', '[\"inapp\"]', 1, 1, ?)",
            (f"s_{uuid.uuid4().hex[:8]}", day),
        )
        return 1
    streak = int(row["streak"] or 0)
    last = row["last_done_date"]
    if last == day:
        return streak
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    streak = streak + 1 if last in (yesterday, day) or not last else 1
    conn.execute(
        "UPDATE subscriptions SET streak = ?, last_done_date = ? WHERE id = ?", (streak, day, row["id"])
    )
    return streak


def _current_streak(conn) -> int:
    row = conn.execute("SELECT streak FROM subscriptions LIMIT 1").fetchone()
    return int(row["streak"]) if row else 0


def recent_doc_ids(days: int) -> dict[str, str]:
    """doc_id → 最近一次出现的日期（用于 90/14 天去重）。"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.publish_date AS d, it.evidence_json AS ev
            FROM items it JOIN issues i ON i.id = it.issue_id
            WHERE i.publish_date >= ?
            """,
            (cutoff,),
        ).fetchall()
    out: dict[str, str] = {}
    for row in rows:
        for ev in json.loads(row["ev"] or "[]"):
            out.setdefault(ev.get("doc_id", ""), row["d"])
    return out


def recent_item_keys(days: int) -> set[str]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT it.domain || ':' || it.title_orig AS k
            FROM items it JOIN issues i ON i.id = it.issue_id
            WHERE i.publish_date >= ? AND it.title_orig IS NOT NULL
            """,
            (cutoff,),
        ).fetchall()
    return {row["k"] for row in rows}


def add_feedback(item_id: str | None, verdict: str, note: str, domain: str | None = None, run_id: str | None = None) -> str:
    fid = f"f_{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO feedback (id, item_id, run_id, domain, verdict, note, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fid, item_id, run_id, domain, verdict, note, _now()),
        )
    return fid


def feedback_rows() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM feedback ORDER BY created_at").fetchall()
    return [dict(row) for row in rows]
