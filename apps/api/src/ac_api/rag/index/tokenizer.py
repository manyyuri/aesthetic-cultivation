"""中文友好分词：NFKC + jieba(search) + 字符二元组 + 数字/西文原样成 token。

索引与查询必须共用同一配置，版本号进 manifest 指纹。
"""

from __future__ import annotations

import re
import unicodedata

VERSION = "v1"

ASCII_RE = re.compile(r"[a-z0-9]+(?:[.\-'/:][a-z0-9]+)*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
STOPWORDS = frozenset(
    "的 了 在 是 和 与 也 有 就 都 而 及 或 之 其 这 那 我 你 他 她 它 们 被 把 为 以 于 对 从 到".split()
)

_jieba = None


def _load_jieba():
    global _jieba
    if _jieba is None:
        try:
            import jieba  # type: ignore

            jieba.setLogLevel(20)
            _jieba = jieba
        except Exception:  # pragma: no cover - 可选依赖
            _jieba = False
    return _jieba


class Tokenizer:
    version = VERSION

    def __init__(self, use_jieba: bool = True) -> None:
        self.use_jieba = use_jieba

    def tokens(self, text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text).lower()
        out: list[str] = []

        for match in ASCII_RE.finditer(text):
            out.append(match.group(0))

        jieba = _load_jieba() if self.use_jieba else None
        for run in CJK_RE.findall(text):
            if jieba:
                out.extend(w for w in jieba.lcut_for_search(run) if w.strip())
            else:
                out.extend(run)
            out.extend(run[i : i + 2] for i in range(len(run) - 1))

        return [t for t in out if t and t not in STOPWORDS]

    def words(self, text: str) -> list[str]:
        """只给词级 token（jieba 词 + ASCII 词），不含字符二元组。用于实体闸门等判断。"""
        text = unicodedata.normalize("NFKC", text).lower()
        out: list[str] = [m.group(0) for m in ASCII_RE.finditer(text)]
        jieba = _load_jieba() if self.use_jieba else None
        for run in CJK_RE.findall(text):
            if jieba:
                out.extend(w for w in jieba.cut(run) if w.strip())
            else:
                out.extend(run)
        return [t for t in out if t and t not in STOPWORDS]

    def fingerprint(self) -> str:
        return f"{VERSION}:{'jieba' if self.use_jieba else 'chars'}"


tokenizer = Tokenizer()
