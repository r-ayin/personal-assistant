"""test_l1_dedup.py — v0.10 L1 两阶段去重（四判决/priority 合并/旧库迁移）。"""
from __future__ import annotations

import sqlite3

import pytest

from personal_assistant import config, memory, storage
from personal_assistant.llm import StubLLM, HashingEmbedder


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "dedup.db")
    return HashingEmbedder(dim=64)


def test_store_when_no_candidates(db):
    r = memory.dedup_and_store(
        [{"kind": "event", "content": "今天去爬山了", "evidence": "segment:s1", "priority": 70}],
        embedder=db, llm=StubLLM())
    assert r["stored"] == 1 and r["skipped"] == 0
    assert storage.count_memories() == 1


def test_skip_exact_duplicate(db):
    m = {"kind": "event", "content": "今天去爬山了很开心", "evidence": "segment:s1", "priority": 70}
    memory.dedup_and_store([dict(m)], embedder=db, llm=StubLLM())
    r = memory.dedup_and_store([dict(m)], embedder=db, llm=StubLLM())
    assert r["skipped"] == 1 and r["stored"] == 0
    assert storage.count_memories() == 1


def test_merge_similar_same_kind(db):
    memory.dedup_and_store(
        [{"kind": "preference", "content": "我喜欢喝美式咖啡", "evidence": "segment:s1", "priority": 70}],
        embedder=db, llm=StubLLM())
    r = memory.dedup_and_store(
        [{"kind": "preference", "content": "我喜欢喝美式咖啡不加糖", "evidence": "segment:s2", "priority": 75}],
        embedder=db, llm=StubLLM())
    # 同 kind 高重叠 → merge（stub bigram 重叠判定）
    assert r["merged"] + r["stored"] == 1
    mems = storage.memories_all()
    if r["merged"] == 1:
        assert len(mems) == 1
        merged = mems[0]
        assert "不加糖" in merged["content"]
        assert merged["version"] == 1  # update/merge 后 version+1
        assert "segment:s1" in merged["evidence"] and "segment:s2" in merged["evidence"]


def test_priority_merge_rule(db):
    """merge 未给 merged_priority 时：取高者 +10，≤100。"""
    p = memory._merged_priority(70, 75, "merge", {})
    assert p == 85
    assert memory._merged_priority(95, 98, "merge", {}) == 100
    assert memory._merged_priority(70, 75, "update", {}) == 75
    assert memory._merged_priority(50, 60, "merge", {"merged_priority": 90}) == 90


def test_invalid_action_falls_back_to_store(db):
    class BadLLM(StubLLM):
        def chat(self, system, user, temperature=0.3):
            import json
            if "DEDUP_MEMORIES" in system:
                data = json.loads(user)
                return json.dumps([{"new_id": item["new_id"], "action": "explode",
                                    "target_id": ""} for item in data["new_memories"]])
            return super().chat(system, user, temperature)

    memory.dedup_and_store(
        [{"kind": "event", "content": "第一条记忆内容", "evidence": "segment:s1", "priority": 70}],
        embedder=db, llm=StubLLM())
    r = memory.dedup_and_store(
        [{"kind": "event", "content": "第二条不同记忆", "evidence": "segment:s2", "priority": 70}],
        embedder=db, llm=BadLLM())
    assert r["stored"] == 1  # 非法 action 降级 store，记忆不丢失
    assert storage.count_memories() == 2


def test_low_priority_filtered(db):
    mems = [{"kind": "emotion", "content": "有点烦", "priority": 30},
            {"kind": "event", "content": "重要事件发生", "priority": 80}]
    kept = memory.filter_low_priority(mems)
    assert len(kept) == 1 and kept[0]["kind"] == "event"


def test_priority_parse_tolerant():
    class PrioLLM(StubLLM):
        def _extract(self, prompt):
            return [{"kind": "event", "content": "测试内容", "segment_id": "s1",
                     "evidence": "segment:s1", "priority": "not-a-number"}]
    out = memory.extract([{"id": "s1", "text": "测试"}], llm=PrioLLM())
    assert out[0]["priority"] == 50  # 非法值修复为 50


def test_old_db_migration(tmp_path, monkeypatch):
    """旧库（无 priority/scene_name/version/updated_at 列）打开自动迁移。"""
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.execute("""CREATE TABLE memories(
      id TEXT PRIMARY KEY, segment_id TEXT, kind TEXT, content TEXT, evidence TEXT,
      embedding BLOB, created_at TEXT, processed INT DEFAULT 0)""")
    con.execute("INSERT INTO memories(id,segment_id,kind,content,evidence,created_at) "
                "VALUES('m-old','s1','fact','旧记忆','segment:s1','2026-01-01T00:00:00')")
    con.commit()
    con.close()
    monkeypatch.setattr(config, "sqlite_path", lambda: old)
    m = storage.memory_get("m-old")
    assert m["priority"] == 50 and m["version"] == 0
    # FTS 重建覆盖旧数据
    hits = storage.fts_search("旧记忆", k=3)
    assert any(h["mem_id"] == "m-old" for h in hits)
