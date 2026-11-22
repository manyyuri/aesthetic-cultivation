"""轻量异步 job：MVP 不引队列，进程内 dict + asyncio.create_task。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str
    kind: str
    status: str = "queued"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    report: Any = None
    error: str | None = None


JOBS: dict[str, Job] = {}


def submit(kind: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    JOBS[job_id] = Job(id=job_id, kind=kind)

    async def runner() -> None:
        job = JOBS[job_id]
        job.status = "running"
        try:
            job.report = await asyncio.to_thread(fn, *args, **kwargs)
            job.status = "done"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)[:400]

    asyncio.create_task(runner())
    return job_id


def get(job_id: str) -> Job | None:
    return JOBS.get(job_id)
