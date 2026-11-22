"""校验 packages/contracts 的生成物与当前后端一致（CI 门禁）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ac_api.app import app  # noqa: E402

path = ROOT / "packages" / "contracts" / "openapi.json"
if not path.exists():
    print("缺少 packages/contracts/openapi.json，先跑 make contracts")
    raise SystemExit(1)

current = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True)
if path.read_text(encoding="utf-8").strip() != current.strip():
    print("契约漂移：请跑 make contracts 并提交生成物")
    raise SystemExit(1)

print("contracts ok")
