from ac_api.rag.retrieve.rerank import LexicalReranker


def test_lexical_reranker_orders_by_coverage():
    scores = LexicalReranker().score(
        "胡桃夹子 首演 剧院",
        ["《胡桃夹子》于 1892 年 12 月 18 日在马林斯基剧院首演。", "这是一段完全无关的话，只是在讲天气。"],
    )
    assert scores[0] > scores[1]
    assert 0 <= scores[1] <= 1
