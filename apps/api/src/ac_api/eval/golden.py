from __future__ import annotations

import json
from pathlib import Path

from ac_api.config import eval_dir


def golden_path(domain: str) -> Path:
    return eval_dir() / "golden" / f"{domain}.jsonl"


def load_golden(domain: str) -> list[dict]:
    path = golden_path(domain)
    if not path.exists():
        raise FileNotFoundError(f"缺少 golden：{path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_golden(domain: str, record: dict) -> None:
    path = golden_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()} if path.exists() else set()
    if record["id"] in existing:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
