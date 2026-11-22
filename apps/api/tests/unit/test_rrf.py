from ac_api.rag.retrieve.rrf import rrf_fuse


def test_rrf_prefers_document_on_both_lists():
    scores, ranks = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["d"]
    assert ranks["a"] == {"bm25": 1, "dense": 2}


def test_rrf_merges_same_id_and_handles_empty():
    scores, _ = rrf_fuse([["a"], []], k=60)
    assert abs(scores["a"] - 1 / 61) < 1e-9
    assert rrf_fuse([[], []])[0] == {}
