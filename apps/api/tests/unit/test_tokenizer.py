from ac_api.rag.index.tokenizer import tokenizer


def test_chinese_query_tokens_overlap_document_tokens():
    # jieba 会把"胡桃夹子组曲"切成 胡桃/夹子/组曲，所以断言的是"两侧有交集"，不是某个固定词
    query = set(tokenizer.tokens("胡桃夹子"))
    doc = set(tokenizer.tokens("胡桃夹子组曲"))
    assert query & doc
    assert "组曲" in doc


def test_ascii_and_opus_preserved():
    tokens = tokenizer.tokens("演奏 Op.71 与 1892 年")
    assert "op.71" in tokens
    assert "1892" in tokens


def test_stopwords_removed_and_bigrams_present():
    tokens = tokenizer.tokens("他的舞会")
    assert "的" not in tokens
    assert "舞会" in tokens
    assert "舞会" in tokenizer.words("他的舞会")


def test_words_excludes_cross_boundary_bigrams():
    words = tokenizer.words("舞的作")
    assert "舞的作" not in words
    assert all(len(w) <= 2 for w in words)
