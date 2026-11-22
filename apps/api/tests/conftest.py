"""测试沙箱：DATA_DIR 指到临时目录，fixtures 复制进去，不碰真实数据。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def sandbox(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("ac-data")
    os.environ["DATA_DIR"] = str(root)
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ["EMBED_PROVIDER"] = "hashed"
    os.environ["RERANK_PROVIDER"] = "lexical"

    import ac_api.config as cfg

    cfg.settings.cache_clear()
    cfg.load_config.cache_clear()

    from ac_api.config import raw_dir
    from ac_api.store.db import init_db

    init_db()
    for domain_dir in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        for path in sorted(domain_dir.glob("*.md")):
            shutil.copy2(path, raw_dir(domain_dir.name) / path.name)

    yield root
    cfg.settings.cache_clear()
    cfg.load_config.cache_clear()
