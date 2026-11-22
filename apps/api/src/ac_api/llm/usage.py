from __future__ import annotations

import json
from datetime import date

from ac_api.config import data_dir


def record(agent: str, prompt_tokens: int, completion_tokens: int, latency_ms: int, run_id: str | None = None) -> None:
    path = data_dir() / "usage"
    path.mkdir(parents=True, exist_ok=True)
    line = {
        "agent": agent,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "run_id": run_id,
    }
    with (path / f"{date.today().isoformat()}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
