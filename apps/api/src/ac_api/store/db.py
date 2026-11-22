from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ac_api.config import db_path

SCHEMA = Path(__file__).with_name("schema.sql")


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = _connect(path or db_path())
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def reset_db(path: Path | None = None) -> None:
    """仅测试用：删库重建。"""
    target = path or db_path()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(target) + suffix)
        if p.exists():
            p.unlink()
    init_db(target)
