"""离线 provider：抽取式回答。不调用任何模型，因此天然不会编造。"""

from __future__ import annotations

import re

from ac_api.rag.index.tokenizer import tokenizer

SENT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?]?")
REFUSAL = "资料里没有能支撑这个问题的原文。可以换个问法，或者告诉我你想知道的年份、版本或编舞家。"

# 这些是"提问用语"，不是实体；判断"问句里的实体在不在证据里"时不算数
GENERIC = frozenset(
    "是谁 什么 哪些 哪个 多少 怎么 怎样 为什么 如何 作用 组成 要点 特点 年份 年代 时间 地点 哪里 在哪 何时 何地 时候 "
    "内容 结构 这部 这个 那部 那个 一下 之后 以前 以后 年 月 日 幕 场 位".split()
)


class StubClient:
    name = "stub"

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        json_mode: bool = False,
        agent: str = "stub",
        run_id: str | None = None,
    ) -> str:
        return ""

    def answer(self, question: str, evidence: list[tuple[str, str, str]]) -> str:
        """evidence: [(citation_id, text)]。

        两道闸门，任一不过就拒答（宁可不答，不要沾边就算）：
          1) 实体闸门：问句里的数字/专名，在整段证据里找不到 ⇒ 拒答。
          2) 覆盖闸门：没有任何一句与问句有实质词元重合 ⇒ 拒答。
        """
        q = sorted({t for t in tokenizer.words(question) if len(t) >= 2 and t not in GENERIC})
        corpus_text = "\n".join(f"{anchor} {text}" for _, anchor, text in evidence)
        corpus_tokens = set(tokenizer.tokens(corpus_text))
        # 年份是硬事实：证据里没有这个年份，就不回答（这是"据说 1990 年"类幻觉的入口）
        if any(year not in corpus_text for year in re.findall(r"\d{4}", question)):
            return REFUSAL
        missing = [t for t in q if t not in corpus_tokens]
        if q and len(missing) / len(q) > 1 / 3:
            return REFUSAL

        scored: list[tuple[float, str, str]] = []
        for citation, _anchor, text in evidence:
            for sentence in SENT_RE.findall(text):
                sentence = sentence.strip()
                if len(sentence) < 12:
                    continue
                tokens = set(tokenizer.tokens(sentence))
                hit = len(set(q) & tokens)
                if hit:
                    scored.append((hit / max(len(q), 1), sentence, citation))
        scored.sort(key=lambda item: -item[0])
        picked: list[tuple[float, str, str]] = []
        seen: set[str] = set()
        for item in scored:
            if item[1] in seen:
                continue
            seen.add(item[1])
            picked.append(item)
            if len(picked) >= 3:
                break
        if not picked:
            return REFUSAL
        return "\n\n".join(
            f"{sentence.rstrip('。！？!?；;')} [{citation}]。" for _, sentence, citation in picked
        )


def get_client():
    from ac_api.config import settings
    from ac_api.llm.deepseek import DeepSeekClient

    if settings().deepseek_api_key and settings().deepseek_model:
        try:
            return DeepSeekClient()
        except Exception:
            pass
    return StubClient()
