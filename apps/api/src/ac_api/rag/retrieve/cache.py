"""检索缓存：请求级 LRU + 任务级（X-Task-Id）。键里含 index_version，换版本自然失效。"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._data[key] = (time.monotonic() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


class RetrieveCache:
    def __init__(self, max_entries: int = 512, ttl_s: int = 600, task_ttl_s: int = 900) -> None:
        self.request = TTLCache(max_entries)
        self.task = TTLCache(max_entries)
        self.ttl_s = ttl_s
        self.task_ttl_s = task_ttl_s

    def get(self, key: str, task_id: str | None) -> tuple[Any, str] | None:
        if task_id:
            hit = self.task.get(f"{task_id}:{key}")
            if hit is not None:
                return hit, "task"
        hit = self.request.get(key)
        return (hit, "request") if hit is not None else None

    def set(self, key: str, value: Any, task_id: str | None) -> None:
        self.request.set(key, value, self.ttl_s)
        if task_id:
            self.task.set(f"{task_id}:{key}", value, self.task_ttl_s)
