from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ac_api.api.deps import require_admin
from ac_api.api.jobs import get as get_job
from ac_api.api.jobs import submit
from ac_api.api.schemas import FeedbackRequest, PromoteRequest
from ac_api.config import eval_dir
from ac_api.store import issues as issues_store

router = APIRouter(prefix="/api/eval", tags=["eval"])


@router.get("/reports")
def reports(domain: str = Query(default="ballet")) -> dict:
    folder = eval_dir() / "reports"
    items = []
    if folder.exists():
        for path in sorted(folder.glob(f"{domain}-*.json"), reverse=True)[:10]:
            items.append({"name": path.name, "report": json.loads(path.read_text(encoding="utf-8"))})
    return {"domain": domain, "reports": items}


@router.post("/run", dependencies=[Depends(require_admin)])
def run(domain: str = Query(default="ballet"), ci: bool = False) -> dict:
    from ac_api.eval.runner import run_domain

    return {"job_id": submit("eval", run_domain, domain, 5, ci)}


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="没有这个 job")
    return record.model_dump()


@router.post("/feedback")
def feedback(body: FeedbackRequest) -> dict:
    fid = issues_store.add_feedback(body.item_id, body.verdict, body.note, body.domain, body.run_id)
    return {"id": fid}


@router.post("/promote", dependencies=[Depends(require_admin)])
def promote(body: PromoteRequest) -> dict:
    from ac_api.eval.runner import promote_item

    return promote_item(body.domain, body.item_id)
