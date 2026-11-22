from __future__ import annotations

from pydantic import BaseModel, Field

from ac_api.domain.models import Issue
from ac_api.push.email import send_email
from ac_api.push.inapp import send_inapp
from ac_api.push.macos import send_macos


class DeliveryReport(BaseModel):
    issue_id: str
    channels: list[str]
    delivered: bool
    results: list[dict] = Field(default_factory=list)


def deliver(issue: Issue, channels: list[str]) -> DeliveryReport:
    results: list[dict] = []
    for channel in channels:
        try:
            if channel == "inapp":
                results.append(send_inapp(issue))
            elif channel == "email":
                results.append(send_email(issue))
            elif channel == "macos":
                results.append(send_macos(issue))
            else:
                results.append({"channel": channel, "ok": False, "reason": "unknown_channel"})
        except Exception as exc:  # 单个渠道失败不影响其他渠道
            results.append({"channel": channel, "ok": False, "reason": str(exc)[:200]})
    delivered = any(r.get("ok") for r in results)
    return DeliveryReport(issue_id=issue.id, channels=channels, delivered=delivered, results=results)
