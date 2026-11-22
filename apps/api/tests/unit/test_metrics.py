from ac_api.eval.metrics import citation_coverage, recall_at_k, reciprocal_rank, refused


def test_recall_and_mrr():
    assert recall_at_k(["x", "a", "b"], ["a"], 2) == 1.0
    assert recall_at_k(["x", "y"], ["a"], 2) == 0.0
    assert reciprocal_rank(["x", "a"], ["a"]) == 0.5
    assert recall_at_k(["x"], [], 5) == 1.0


def test_citation_coverage_counts_only_valid_ids():
    answer = "甲 [S1]。乙 [S9]。丙。"
    # 只有"甲 [S1]"是合规引用：乙引用了不存在的 S9，丙没有引用
    assert citation_coverage(answer, {"S1", "S2"}) == 1 / 3


def test_refused_requires_no_key_fact_leak():
    assert refused("资料里没有能支撑这个问题的原文。", ["2023"]) is True
    assert refused("资料里没有，但可能是 2023 年。", ["2023"]) is False


def test_refused_ignores_negated_cited_sentence():
    # 拒答时会把问题里的词复述一遍（"资料里没有卢浮宫的…"），那不算编造
    answer = "资料里没有关于卢浮宫收藏的著录信息 [S1]。现有证据只涉及《星月夜》 [S2]。"
    assert refused(answer, ["卢浮宫"]) is True
    # 但把关键事实写进带引用的断言，就是编造
    assert refused("卢浮宫收藏了这件作品 [S1]。资料里没有其它信息。", ["卢浮宫"]) is False
