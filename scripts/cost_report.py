"""按 data/usage/*.jsonl 汇总当日 token 与成本。单价从 env 读，不写死（官方会调价）。"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ac_api.config import data_dir  # noqa: E402


def main(day: str | None = None) -> None:
    day = day or date.today().isoformat()
    path = data_dir() / "usage" / f"{day}.jsonl"
    if not path.exists():
        print(f"没有 {day} 的用量记录（{path}）")
        return
    per_agent: dict[str, dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0, "calls": 0})
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        bucket = per_agent[row.get("agent", "?")]
        bucket["prompt"] += int(row.get("prompt_tokens", 0))
        bucket["completion"] += int(row.get("completion_tokens", 0))
        bucket["calls"] += 1

    price_in = float(os.environ.get("PRICE_INPUT_PER_M", "0"))
    price_out = float(os.environ.get("PRICE_OUTPUT_PER_M", "0"))
    print(f"== {day} ==")
    total = 0.0
    for agent, b in sorted(per_agent.items()):
        cost = b["prompt"] / 1e6 * price_in + b["completion"] / 1e6 * price_out
        total += cost
        print(
            f"  {agent:<10} calls={b['calls']:<4} in={b['prompt']:<8} out={b['completion']:<8} "
            f"cost={cost:.4f}"
        )
    if price_in == 0 and price_out == 0:
        print("  （未设置 PRICE_INPUT_PER_M / PRICE_OUTPUT_PER_M，成本按 0 计）")
    print(f"  total cost = {total:.4f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
