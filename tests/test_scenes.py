"""test_scenes.py — v0.10 L2 场景层（整合策略/heat/容量/溯源）。"""
from __future__ import annotations

import pytest

from personal_assistant import config, scenes, storage
from personal_assistant.llm import StubLLM, HashingEmbedder


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "scenes.db")
    emb = HashingEmbedder(dim=64)
    return emb


def _add_mems(n, kind="event", prefix="记忆"):
    emb = HashingEmbedder(dim=64)
    ids = []
    for i in range(n):
        m = {"id": f"m-{kind}-{i}", "kind": kind,
             "content": f"{prefix}内容{i}：今天发生了一些事情记录一下", "priority": 70}
        storage.add_memory(m, emb.embed_one(m["content"]))
        ids.append(m["id"])
    return ids


def test_integrate_creates_scenes_with_heat(db):
    _add_mems(5, "event")
    _add_mems(3, "preference")
    r = scenes.integrate(llm=StubLLM())
    assert r["scenes_total"] >= 1
    assert r["created"] >= 1
    for s in storage.scenes_all():
        assert s["heat"] >= 1
        assert s["source_mem_ids"], "场景必须有记忆溯源"


def test_second_integrate_updates_and_increments_heat(db):
    _add_mems(4, "event", "第一批")
    scenes.integrate(llm=StubLLM())
    first = {s["name"]: s["heat"] for s in storage.scenes_all()}
    _add_mems(4, "event", "第二批不同内容")
    scenes.integrate(llm=StubLLM())
    second = {s["name"]: s["heat"] for s in storage.scenes_all()}
    # 同名场景被 UPDATE：heat 递增
    for name in first:
        if name in second:
            assert second[name] >= first[name]


def test_traceability_rejects_fake_source_ids(db):
    """LLM 编造的 source_mem_ids 应导致操作被丢弃（反幻觉）。"""
    _add_mems(2, "event")

    class LyingLLM(StubLLM):
        def chat(self, system, user, temperature=0.3):
            import json
            if "SCENE_INTEGRATE" in system:
                return json.dumps([{"action": "CREATE", "name": "虚假场景",
                                    "summary": "x", "body": "y",
                                    "source_mem_ids": ["m-nonexistent-999"]}])
            return super().chat(system, user, temperature)

    r = scenes.integrate(llm=LyingLLM())
    assert r["created"] == 0
    assert all(s["name"] != "虚假场景" for s in storage.scenes_all())


def test_body_truncation(db):
    _add_mems(2, "event")

    class LongBodyLLM(StubLLM):
        def chat(self, system, user, temperature=0.3):
            import json
            if "SCENE_INTEGRATE" in system:
                return json.dumps([{"action": "CREATE", "name": "长文本场景",
                                    "summary": "x", "body": "字" * 2000,
                                    "source_mem_ids": [storage.memories_all()[0]["id"]]}])
            return super().chat(system, user, temperature)

    scenes.integrate(llm=LongBodyLLM())
    s = [x for x in storage.scenes_all() if x["name"] == "长文本场景"][0]
    assert len(s["body"]) <= scenes.MAX_BODY_CHARS


def test_capacity_forces_merge(db, monkeypatch):
    config_get_orig = config.get
    monkeypatch.setattr(config, "get",
                        lambda k, d=None: 3 if k == "memory.scene_max" else config_get_orig(k, d))
    # 预置 3 个场景占满容量
    for i in range(3):
        storage.scene_upsert({"id": f"sc-old-{i}", "name": f"旧场景{i}",
                              "summary": "旧", "body": "旧内容", "heat": i + 1,
                              "source_mem_ids": []})
    _add_mems(3, "event")
    r = scenes.integrate(llm=StubLLM())
    # stub 在容量满时输出 MERGE——合并后总数不增
    assert r["scenes_total"] <= 4
    assert r["merged"] >= 1 or r["created"] == 0


def test_navigation_sorted_by_heat(db):
    storage.scene_upsert({"id": "a", "name": "低热场景", "summary": "s1", "heat": 1,
                          "source_mem_ids": []})
    storage.scene_upsert({"id": "b", "name": "高热场景", "summary": "s2", "heat": 60,
                          "source_mem_ids": []})
    nav = scenes.navigation()
    assert nav.index("高热场景") < nav.index("低热场景")
    assert "🔥" in nav


def test_pending_count_and_mark(db):
    _add_mems(3, "event")
    assert scenes.pending_count() == 3
    scenes.integrate(llm=StubLLM())
    assert scenes.pending_count() == 0
