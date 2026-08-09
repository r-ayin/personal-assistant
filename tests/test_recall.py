"""test_recall.py — v0.10 混合召回（BM25+向量+RRF+预算）单测。"""
from __future__ import annotations

import pytest

from personal_assistant import config, recall, storage
from personal_assistant.llm import HashingEmbedder


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "recall.db")
    emb = HashingEmbedder(dim=64)
    mems = [
        {"id": "m-run", "kind": "preference", "content": "我喜欢每天早晨跑步", "priority": 80},
        {"id": "m-cat", "kind": "fact", "content": "我养了一只叫小黑的猫", "priority": 70},
        {"id": "m-trip", "kind": "event", "content": "上周和朋友去爬山了", "priority": 65},
    ]
    for m in mems:
        storage.add_memory(m, emb.embed_one(m["content"]))
    return emb


def test_bm25_chinese_bigram_hit(db):
    hits = storage.fts_search("跑步", k=5)
    assert any(h["mem_id"] == "m-run" for h in hits)


def test_hybrid_dual_source_scores_higher(db):
    rr = recall.hybrid_recall("我喜欢跑步", k=5)
    assert rr.items
    top = rr.items[0]
    assert top["memory"]["id"] == "m-run"
    # 双榜命中 sources 含两路，且分数高于单路基准 1/(60+1)
    if "bm25" in top["sources"] and "vector" in top["sources"]:
        assert top["score"] > 1.0 / 61


def test_rrf_fuse_math():
    a = [{"memory": {"id": "x"}}, {"memory": {"id": "y"}}]
    b = [{"memory": {"id": "y"}}, {"memory": {"id": "z"}}]
    fused = recall.rrf_fuse([a, b])
    scores = {f["memory"]["id"]: f["score"] for f in fused}
    # y 双榜命中（rank 从 0 计）：1/(60+1+1) + 1/(60+0+1)
    assert scores["y"] > scores["x"]
    assert scores["y"] > scores["z"]
    assert scores["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[0]["memory"]["id"] == "y"
    assert set(fused[0]["sources"]) == {"bm25", "vector"}


def test_budget_max_results(db):
    rr = recall.hybrid_recall("我", k=2, budget={"score_threshold": 0.0})
    assert len(rr.items) <= 2


def test_budget_total_chars_truncates(db):
    # 两条候选各 9 字符；总预算 12 → 第一条完整、第二条因剩余<40 被丢弃
    rr = recall.hybrid_recall("我 猫 跑步 爬山", k=5,
                              budget={"score_threshold": 0.0, "max_total_chars": 12})
    assert len(rr.items) == 1
    assert rr.truncated


def test_timeout_returns_structured(db):
    rr = recall.hybrid_recall("跑步", k=5, budget={"timeout_ms": 0})
    assert isinstance(rr.elapsed_ms, float)
    assert rr.truncated or rr.items is not None


def test_strategy_keyword_only(db):
    rr = recall.hybrid_recall("跑步", strategy="keyword")
    assert rr.strategy == "keyword"
    for it in rr.items:
        assert "vector" not in it["sources"]


def test_strategy_embedding_only(db):
    rr = recall.hybrid_recall("跑步", strategy="embedding")
    assert rr.strategy == "embedding"
    for it in rr.items:
        assert "bm25" not in it["sources"]


def test_recall_result_to_dict(db):
    rr = recall.hybrid_recall("跑步", k=3)
    d = rr.to_dict()
    assert set(d.keys()) == {"items", "truncated", "elapsed_ms", "strategy"}
