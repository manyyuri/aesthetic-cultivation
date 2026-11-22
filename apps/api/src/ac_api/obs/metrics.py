"""进程内 Prometheus 指标（零依赖）：counter / gauge / histogram → /metrics 文本。"""

from __future__ import annotations

import math
import threading
from collections import defaultdict
from typing import Iterable

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((labels or {}).items()))


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple], float] = {}
        self._hist: dict[tuple[str, tuple], list[float]] = defaultdict(list)
        self._buckets: dict[str, Iterable[float]] = {}

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        with self._lock:
            self._counters[(name, _labels_key(labels))] += value

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[(name, _labels_key(labels))] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: Iterable[float] = DEFAULT_BUCKETS,
    ) -> None:
        with self._lock:
            self._hist[(name, _labels_key(labels))].append(value)
            self._buckets[name] = tuple(buckets)

    def _fmt_labels(self, labels: tuple) -> str:
        if not labels:
            return ""
        inner = ",".join(f'{k}="{v}"' for k, v in labels)
        return "{" + inner + "}"

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{self._fmt_labels(labels)} {value:g}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{self._fmt_labels(labels)} {value:g}")
            for (name, labels), values in sorted(self._hist.items()):
                buckets = self._buckets.get(name, DEFAULT_BUCKETS)
                lines.append(f"# TYPE {name} histogram")
                for b in buckets:
                    count = sum(1 for v in values if v <= b)
                    lines.append(f'{name}_bucket{self._fmt_labels(labels + (("le", f"{b:g}"),))} {count}')
                lines.append(
                    f'{name}_bucket{self._fmt_labels(labels + (("le", "+Inf"),))} {len(values)}'
                )
                lines.append(f"{name}_sum{self._fmt_labels(labels)} {sum(values):g}")
                lines.append(f"{name}_count{self._fmt_labels(labels)} {len(values)}")
        return "\n".join(lines) + ("\n" if lines else "")

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            out = {f"{name}{self._fmt_labels(labels)}": v for (name, labels), v in self._counters.items()}
            out.update({f"{name}{self._fmt_labels(labels)}": v for (name, labels), v in self._gauges.items()})
            return out

    def histogram_stats(self, name: str) -> dict[str, float]:
        with self._lock:
            values = [v for (n, _), vals in self._hist.items() if n == name for v in vals]
        if not values:
            return {}
        values.sort()
        p95 = values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]
        return {"count": len(values), "p50": values[len(values) // 2], "p95": p95, "max": values[-1]}


metrics = Metrics()
