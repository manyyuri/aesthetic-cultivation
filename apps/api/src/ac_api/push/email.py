"""邮件推送：单列 600px、inline CSS、无外部字体。邮件里也保留 № 编号与证据链接。"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from html import escape

from ac_api.config import settings
from ac_api.domain.models import Issue


def render_email(issue: Issue, base_url: str = "http://127.0.0.1:5173") -> str:
    rows: list[str] = []
    for item in issue.items:
        meta = " · ".join(f"{m.v}" for m in item.meta_lines)
        mark = item.evidence[0].mark if item.evidence else ""
        rows.append(
            f"""
      <tr><td style="padding:28px 32px;border-top:1px solid #D3D3CC">
        <div style="font-family:'SF Mono',monospace;font-size:11px;letter-spacing:.14em;color:#6B6B63">
          {_roman(item.ord)} · {escape(item.domain)} · <span style="font-family:'SF Mono',monospace">{escape(mark)}</span>
        </div>
        <div style="font-family:'Songti SC',Songti,serif;font-size:22px;line-height:1.3;margin:8px 0 2px">
          {escape(item.title_zh)}
        </div>
        <div style="font-family:Georgia,serif;font-style:italic;font-size:14px;color:#3A3A34">
          {escape(item.title_orig or "")}
        </div>
        <div style="font-family:'SF Mono',monospace;font-size:12px;color:#6B6B63;margin:10px 0 14px">
          {escape(meta)}
        </div>
        <div style="font-family:-apple-system,'PingFang SC',sans-serif;font-size:15px;line-height:1.8;max-width:34em">
          {escape(item.hook)}
        </div>
        <div style="font-family:'SF Mono',monospace;font-size:12px;color:#6B6B63;margin-top:14px">
          {escape(item.anchor.label)}
        </div>
        <div style="margin-top:18px">
          <a href="{base_url}/item/{item.id}"
             style="font-family:-apple-system,'PingFang SC',sans-serif;font-size:14px;color:#EDEDEA;
                    background:#12120F;padding:9px 18px;text-decoration:none;display:inline-block">
            读这一段
          </a>
        </div>
      </td></tr>"""
        )
    return f"""<!doctype html><html><body style="margin:0;background:#E4E4DF">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#E4E4DF;padding:24px 0">
   <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#EDEDEA">
     <tr><td style="padding:32px 32px 8px">
       <div style="font-family:'SF Mono',monospace;font-size:11px;letter-spacing:.14em;color:#6B6B63">
         第 {issue.issue_no:03d} 期 · {escape(issue.publish_date)} · 今夜 {issue.minutes} 分钟
       </div>
       <div style="font-family:'Songti SC',Songti,serif;font-size:34px;letter-spacing:-.02em;margin:14px 0 6px">
         {escape(issue.title)}
       </div>
       <div style="font-family:-apple-system,'PingFang SC',sans-serif;font-size:14px;color:#3A3A34;line-height:1.8">
         {escape(issue.subtitle)}
       </div>
     </td></tr>
     {''.join(rows)}
     <tr><td style="padding:24px 32px 32px;border-top:1px solid #D3D3CC;
                    font-family:'SF Mono',monospace;font-size:11px;color:#6B6B63">
       每一句都有出处。点 № 编号可回看原文。
     </td></tr>
    </table>
   </td></tr>
  </table>
</body></html>"""


def _roman(n: int) -> str:
    return {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ", 5: "Ⅴ", 6: "Ⅵ"}.get(n, str(n))


def send_email(issue: Issue) -> dict:
    s = settings()
    if not s.smtp_host or not s.push_email_to:
        return {"channel": "email", "ok": False, "reason": "smtp_not_configured"}
    message = EmailMessage()
    message["Subject"] = f"第 {issue.issue_no:03d} 期 · {issue.title} · {issue.publish_date}"
    message["From"] = s.smtp_user or f"aesthetic-cultivation@{s.smtp_host}"
    message["To"] = s.push_email_to
    message.set_content(f"{issue.title}\n{issue.subtitle}\n\n共 {len(issue.items)} 件，约 {issue.minutes} 分钟。")
    message.add_alternative(render_email(issue), subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        if s.smtp_port != 25:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_pass)
        smtp.send_message(message)
    return {"channel": "email", "ok": True, "to": s.push_email_to}
