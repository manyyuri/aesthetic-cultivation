from __future__ import annotations

from ac_api.domain.models import Issue


def send_inapp(issue: Issue) -> dict:
    """站内渠道：内容已在库里，这里只做可用性确认。"""
    return {"channel": "inapp", "ok": True, "items": len(issue.items)}
