from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ac_api.config import chunks_dir


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


def manifest_path(domain: str) -> Path:
    return chunks_dir(domain) / "_manifest.json"


def load_manifest(domain: str) -> dict:
    path = manifest_path(domain)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(domain: str, data: dict) -> None:
    path = manifest_path(domain)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
