from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from ac_api.app import app
from ac_api.config import data_dir

ALLOWED = "https://images.metmuseum.org/CRDImages/gr/web-large/DP350061.jpg"


def test_unauthorized_host_refused():
    with TestClient(app) as client:
        resp = client.get("/api/media", params={"src": "https://evil.example/x.jpg"})
    assert resp.status_code == 400
    with TestClient(app) as client:
        resp = client.get("/api/media", params={"src": "http://images.metmuseum.org/x.jpg"})
    assert resp.status_code == 400


class _FakeResponse:
    content = b"\xff\xd8\xff\xe0fake-jpeg"
    headers = {"content-type": "image/jpeg"}

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url):
        return _FakeResponse()


def test_allowed_host_cached_after_first_fetch(monkeypatch, sandbox):
    import ac_api.api.routes_media as media

    cache_file = media.media_cache_path(ALLOWED)
    if cache_file.exists():
        cache_file.unlink()
    if cache_file.with_suffix(".type").exists():
        cache_file.with_suffix(".type").unlink()

    monkeypatch.setattr(media.httpx, "Client", _FakeClient)
    with TestClient(app) as client:
        first = client.get("/api/media", params={"src": ALLOWED})
        second = client.get("/api/media", params={"src": ALLOWED})
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("image/jpeg")
    assert second.status_code == 200
    assert cache_file.exists()
    assert cache_file.stat().st_size == len(_FakeResponse.content)
    assert cache_file.is_relative_to(data_dir())
