from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    domain: str
    force: bool = False


class IndexRequest(BaseModel):
    domain: str


class RollbackRequest(BaseModel):
    domain: str
    index_version: str


class FetchRequest(BaseModel):
    source: str
    limit: int = Field(default=10, ge=1, le=100)
    query: str | None = None
    dry_run: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    client_request_id: str | None = None


class DoneRequest(BaseModel):
    done: bool = True


class SubscribeUpdate(BaseModel):
    kind: str = Field(default="daily", pattern="^(daily|weekly)$")
    time_of_day: str = Field(default="07:30", pattern=r"^\d{2}:\d{2}$")
    channels: list[str] = Field(default_factory=lambda: ["inapp"])
    active: bool = True


class FeedbackRequest(BaseModel):
    item_id: str | None = None
    run_id: str | None = None
    domain: str | None = None
    verdict: str = Field(pattern="^(hallucination|wrong_citation|missing_evidence|ok)$")
    note: str = ""


class PromoteRequest(BaseModel):
    domain: str
    run_id: str | None = None
    item_id: str | None = None


class HitlRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = ""
