"""run 追踪：落库（trace 页/重放）+ 可选事件汇（SSE）。"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Callable

from ac_api.store import runs as runs_store


def _ts() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Tracer:
    def __init__(self, run_id: str, emit: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.run_id = run_id
        self.emit = emit
        self.seq = 0

    def _next(self) -> int:
        self.seq += 1
        return self.seq

    def event(self, type_: str, **data: Any) -> dict[str, Any]:
        payload = {"seq": self._next(), "ts": _ts(), "type": type_, **data}
        if self.emit:
            self.emit(payload)
        return payload

    def started(self, step: str, label: str) -> dict[str, Any]:
        return self.event("step.started", step=step, label=label)

    def step(
        self,
        step: str,
        *,
        ok: bool = True,
        latency_ms: int = 0,
        summary: str = "",
        payload: dict[str, Any] | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        runs_store.log_step(
            self.run_id,
            self._next(),
            step,
            status="ok" if ok else "fail",
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            payload=payload,
        )
        self.event(
            "step.finished",
            step=step,
            ok=ok,
            latency_ms=latency_ms,
            summary=summary,
            payload=payload,
        )


class Timer:
    def __enter__(self) -> "Timer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, *exc) -> None:
        self.ms = int((time.monotonic() - self._t0) * 1000)
