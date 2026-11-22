"""答疑：编排器与评测共用同一条回答路径。

有 key 时走模型（严格按 evidence、逐句带 [S#]），没 key 时走抽取式 stub。
两条路径的输出形状一致，评测才比得出来。
"""

from __future__ import annotations

import json
from typing import Protocol, Sequence

from ac_api.orchestrator.prompts import read_prompt

Evidence = Sequence[tuple[str, str, str]]


class SupportsChat(Protocol):
    def chat(self, system: str, user: str, **kwargs) -> str: ...


def build_payload(question: str, evidence: Evidence) -> str:
    return json.dumps(
        {
            "question": question,
            "evidence": [
                {"id": citation, "section": section, "text": text[:900]}
                for citation, section, text in evidence
            ],
        },
        ensure_ascii=False,
    )


def answer_question(
    question: str,
    evidence: Evidence,
    client: SupportsChat,
    *,
    run_id: str | None = None,
) -> str:
    if hasattr(client, "answer"):  # 离线 stub
        return client.answer(question, evidence)  # type: ignore[attr-defined]
    return client.chat(
        read_prompt("answer"),
        build_payload(question, evidence),
        agent="answer",
        run_id=run_id,
        temperature=0.2,
        max_tokens=2000,
    )
