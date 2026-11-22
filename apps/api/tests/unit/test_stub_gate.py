from ac_api.llm.stub import REFUSAL, StubClient

EVIDENCE = [
    ("S1", "首演与版本记录", "《胡桃夹子》于 1892 年 12 月 18 日在马林斯基剧院首演，与歌剧《伊奥兰塔》在同一晚演出。"),
    ("S2", "第二幕 · 糖果王国", "双人舞是整部作品的重心，慢板由大提琴与钢片琴引出，随后进入变奏与终曲。"),
]


def test_answerable_question_gets_citations():
    answer = StubClient().answer("《胡桃夹子》首演年份与剧院", EVIDENCE)
    assert "1892" in answer
    assert "[S1]" in answer
    assert answer != REFUSAL


def test_missing_year_refuses_instead_of_guessing():
    answer = StubClient().answer("2023 年新版演出的服装设计师是谁", EVIDENCE)
    assert answer == REFUSAL


def test_unrelated_question_refuses():
    answer = StubClient().answer("这首歌的鼓手是谁", EVIDENCE)
    assert answer == REFUSAL
