from __future__ import annotations

import subprocess

from ac_api.domain.models import Issue


def send_macos(issue: Issue) -> dict:
    title = f"第 {issue.issue_no} 期 · {issue.title}"
    body = issue.subtitle[:120]
    script = (
        f'display notification "{body}" with title "{title}" '
        f'subtitle "今夜 {issue.minutes} 分钟" sound name "Glass"'
    )
    completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    return {"channel": "macos", "ok": completed.returncode == 0, "reason": completed.stderr[:200] or None}
