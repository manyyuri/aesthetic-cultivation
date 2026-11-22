"""SSE 事件汇：按 run_id 分发；断线重连由前端用 Last-Event-ID 另走重放。"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


def format_sse(event: dict[str, Any]) -> str:
    seq = event.get("seq", 0)
    return f"id: {seq}\nevent: {event.get('type', 'message')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


class RunHub:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._tasks: dict[str, asyncio.Task] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subs[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        if run_id in self._subs and queue in self._subs[run_id]:
            self._subs[run_id].remove(queue)
        if run_id in self._subs and not self._subs[run_id]:
            self._subs.pop(run_id, None)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        for queue in list(self._subs.get(run_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def spawn(self, run_id: str, coro) -> None:
        if run_id in self._tasks and not self._tasks[run_id].done():
            return
        self._tasks[run_id] = asyncio.create_task(coro)


hub = RunHub()
