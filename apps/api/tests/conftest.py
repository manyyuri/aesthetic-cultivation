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


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    """需要"全新空库"的抓取测试用它：每个测试一个 DATA_DIR，互不干扰。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import ac_api.config as cfg
    from ac_api.store.db import init_db

    cfg.settings.cache_clear()
    cfg.load_config.cache_clear()
    init_db()
    yield tmp_path
    cfg.settings.cache_clear()
    cfg.load_config.cache_clear()


class FakeHttp:
    """按 key 子串匹配的假 HTTP：单测零网络。"""

    def __init__(self, json_map: dict[str, dict], text_map: dict[str, str] | None = None) -> None:
        self.json_map = json_map
        self.text_map = text_map or {}
        self.calls: list[str] = []

    def _pick(self, mapping: dict, key: str):
        for needle, payload in mapping.items():
            if needle in key:
                return payload
        raise AssertionError(f"FakeHttp 没配这个 key：{key}（已配：{list(mapping)}）")

    def get_json(self, url: str, params=None, cache_key: str | None = None):
        key = cache_key or url
        self.calls.append(key)
        return self._pick(self.json_map, key)

    def get_text(self, url: str, cache_key: str | None = None) -> str:
        key = cache_key or url
        self.calls.append(key)
        return self._pick(self.text_map, key)


@pytest.fixture
def fake_http():
    return FakeHttp
