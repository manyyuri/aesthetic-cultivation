"""导出 FastAPI OpenAPI 到 packages/contracts/openapi.json。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from ac_api.app import app  # noqa: E402

target = ROOT / "packages" / "contracts" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
print(f"openapi → {target.relative_to(ROOT)}")
