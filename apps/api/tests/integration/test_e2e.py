"""端到端：ingest → index → retrieve → issue。沙箱 DATA_DIR，不碰真实数据。"""

from __future__ import annotations

from datetime import date

import pytest

from ac_api.config import UnknownDomain, load_config
from ac_api.domain.models import RetrieveRequest
from ac_api.rag.index.builder import build_index
from ac_api.rag.ingest.pipeline import ingest_domain, load_chunks
from ac_api.rag.retrieve.filters import FilterError
from ac_api.rag.retrieve.pipeline import Retriever


@pytest.fixture(scope="module")
def indexed():
    retriever = Retriever()
    for domain in ("ballet", "music", "art"):
        report = ingest_domain(domain, force=True)
        assert report.chunks_total > 0
        build_index(domain)
    return retriever


def test_ballet_recall_hits_premiere_fact(indexed: Retriever):
    res = indexed.retrieve(RetrieveRequest(domain="ballet", query="《胡桃夹子》首演年份与剧院", top_k=4))
    assert res.evidence_status == "found"
    assert res.chunks
    top = res.chunks[0]
    assert top.domain == "ballet"
    assert top.metadata["premiere_year"] == 1892
    assert "1892" in top.content
    assert top.source.startswith("《")


def test_citation_ids_are_sequential(indexed: Retriever):
    res = indexed.retrieve(RetrieveRequest(domain="music", query="勃拉姆斯 第四交响曲 终曲 恰空", top_k=4))
    assert [c.citation_id for c in res.chunks] == [f"S{i}" for i in range(1, len(res.chunks) + 1)]


def test_insufficient_returns_hint_not_error(indexed: Retriever):
    res = indexed.retrieve(RetrieveRequest(domain="ballet", query="悉尼歌剧院 2024 年票价", top_k=4))
    if res.evidence_status == "insufficient":
        assert res.missing_hint
    assert res.chunks == [] or res.evidence_status in ("found", "weak")


def test_domains_are_isolated(indexed: Retriever):
    res = indexed.retrieve(RetrieveRequest(domain="art", query="糖果王国 编舞版本", top_k=5))
    assert all(chunk.domain == "art" for chunk in res.chunks)


def test_invalid_domain_and_filter(indexed: Retriever):
    with pytest.raises(UnknownDomain):
        indexed.retrieve(RetrieveRequest(domain="opera", query="x"))
    with pytest.raises(FilterError):
        indexed.retrieve(
            RetrieveRequest(domain="ballet", query="首演", meta_filter={"dynasty": "唐"})
        )


def test_cache_hits_on_second_identical_query(indexed: Retriever):
    req = RetrieveRequest(domain="ballet", query="影子王国 多少舞者", top_k=3, task_id="t-test")
    first = indexed.retrieve(req)
    second = indexed.retrieve(req)
    assert second.cache_hit is True
    assert second.cache_scope == "task"
    assert first.request_id != second.request_id


def test_issue_build_produces_three_grounded_items(indexed: Retriever):
    from ac_api.orchestrator.core import build_issue

    today = date.today().isoformat()
    issue = build_issue(today, kind="daily")
    assert issue.status in ("ready", "partial")
    assert 1 <= len(issue.items) <= 3
    assert [i.ord for i in issue.items] == list(range(1, len(issue.items) + 1))
    for item in issue.items:
        assert item.evidence, f"{item.title_zh} 没有出处"
        assert item.hook and len(item.hook) <= 60
        assert item.anchor.label
    # 重新生成同一天：草稿可覆盖，但期号不跳
    again = build_issue(today, kind="daily")
    assert again.issue_no == issue.issue_no


def test_mark_done_updates_progress(indexed: Retriever):
    from ac_api.orchestrator.core import build_issue
    from ac_api.store import issues as store

    issue = build_issue(date.today().isoformat(), kind="daily")
    item = issue.items[0]
    issue_id, done_count, _streak = store.mark_item_done(item.id, True)
    assert issue_id == issue.id
    assert done_count == 1
    reloaded = store.get_issue_by_id(issue.id)
    assert reloaded and reloaded.items[0].done_at is not None


def test_domain_config_requires_meta():
    config = load_config()
    for spec in config.domains.values():
        assert spec.required_meta
        assert spec.chunker in ("act_scene", "work_version", "entry")


def test_every_indexed_chunk_has_required_meta():
    config = load_config()
    for domain, spec in config.domains.items():
        for chunk in load_chunks(domain):
            missing = [k for k in spec.required_meta if chunk.metadata.get(k) in (None, "")]
            assert not missing, f"{chunk.chunk_id} 缺 {missing}"
