"""把 apps/api/tests/fixtures 下的公有领域摘录灌进 data/raw，可重复执行。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API / "src"))

from ac_api.config import raw_dir  # noqa: E402


def main() -> None:
    fixtures = API / "tests" / "fixtures"
    total = 0
    for domain_dir in sorted(p for p in fixtures.iterdir() if p.is_dir()):
        target = raw_dir(domain_dir.name)
        for path in sorted(domain_dir.glob("*.md")):
            shutil.copy2(path, target / path.name)
            total += 1
        print(f"{domain_dir.name}: {len(list(domain_dir.glob('*.md')))} docs → {target}")
    print(f"seeded {total} docs")


if __name__ == "__main__":
    main()
