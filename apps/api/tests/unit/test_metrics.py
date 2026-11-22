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
