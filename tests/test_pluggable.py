"""test_pluggable.py — 可插拔接口单测：工厂切换 + stub 合约 + 接口不变量。

GATES.md CRITICAL: "stub/real 后端互换不影响管线"——本文件验证所有 4 个可插拔轴
（LLM/Embedder/ASR/Speaker）的工厂路由、stub 输出合约、接口维度。
零网络零 GPU，纯 stub/hashing 后端。
"""
from __future__ import annotations
import json
import os
import pytest
import numpy as np

from personal_assistant import config
from personal_assistant.llm import (
    LLMClient, Embedder, StubLLM, HashingEmbedder,
    OpenAICompatLLM, AnthropicProxyLLM, OpenAICompatEmbedder,
    get_llm, get_embedder, extract_json,
)
from personal_assistant.asr import (
    Transcriber, StubTranscriber, Segment, get_transcriber,
)
from personal_assistant.speaker import (
    Diarizer, TextDiarizer, get_diarizer,
)
from personal_assistant.transcript import Utterance


# ── extract_json ──────────────────────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_fenced(self):
        assert extract_json('blah\n```json\n[1,2]\n```\nmore') == [1, 2]

    def test_embedded_object(self):
        assert extract_json('here is the answer: {"x": true} done') == {"x": True}

    def test_none_on_empty(self):
        assert extract_json("") is None
        assert extract_json(None) is None

    def test_none_on_garbage(self):
        assert extract_json("no json here at all") is None


# ── LLM factory ───────────────────────────────────────────────────

class TestLLMFactory:
    def test_stub_default(self):
        llm = get_llm()
        assert isinstance(llm, StubLLM)
        assert isinstance(llm, LLMClient)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PA_LLM_BACKEND", "stub")
        config.CONFIG.update(config.load_config())
        llm = get_llm()
        assert isinstance(llm, StubLLM)

    def test_unknown_raises(self, monkeypatch):
        monkeypatch.setitem(config.CONFIG, "llm", {"backend": "nonexistent"})
        with pytest.raises(ValueError, match="nonexistent"):
            get_llm()


# ── StubLLM contract ─────────────────────────────────────────────

class TestStubLLM:
    @pytest.fixture
    def llm(self):
        return StubLLM()

    def test_chat_returns_string(self, llm):
        reply = llm.chat("system", "hello")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_extract_memories(self, llm):
        segs = [{"id": "s1", "text": "今天和朋友去爬山了，很开心。"},
                {"id": "s2", "text": "我喜欢读历史书。"},
                {"id": "s3", "text": "明天打算去看电影。"}]
        prompt = f"[TASK:EXTRACT_MEMORIES]\nSegments (JSON):\n{json.dumps(segs)}"
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)
        assert len(result) >= 3
        for m in result:
            assert "kind" in m
            assert "content" in m
            assert "segment_id" in m
            assert m["kind"] in ("event", "preference", "intention", "emotion", "fact", "skill")

    def test_distill(self, llm):
        mems = [{"kind": "event", "content": "去爬山"},
                {"kind": "preference", "content": "喜欢历史"}]
        prompt = f"[TASK:DISTILL]\nRecent memories (JSON):\n{json.dumps(mems)}"
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, dict)
        assert "profile" in result
        profile = result["profile"]
        for key in ("personality", "values", "goals", "habits", "skills",
                    "knowledge", "thinking_patterns", "preferences", "affective_baseline"):
            assert key in profile, f"profile missing dimension: {key}"

    def test_extract_events(self, llm):
        segs = [{"id": "s1", "text": "明天下午三点开会", "speaker": "user"},
                {"id": "s2", "text": "天气真好", "speaker": "user"}]
        prompt = f"[TASK:EXTRACT_EVENTS]\nUtterances (JSON):\n{json.dumps(segs)}"
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)
        assert any(e.get("when_raw") for e in result)

    def test_extract_reminders(self, llm):
        segs = [{"id": "s1", "text": "每天早上提醒我跑步", "speaker": "user"},
                {"id": "s2", "text": "明天要交报告", "speaker": "user"}]
        prompt = f"[TASK:EXTRACT_REMINDERS]\nUtterances (JSON):\n{json.dumps(segs)}"
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)

    def test_chat_json(self, llm):
        segs = [{"id": "s1", "text": "示例"}]
        prompt = f"[TASK:EXTRACT_MEMORIES]\nSegments (JSON):\n{json.dumps(segs)}"
        result = llm.chat_json("", prompt)
        assert isinstance(result, list)

    def test_recommend_with_results(self, llm):
        prof = {"preferences": ["读书"], "personality": "内向"}
        results = [{"title": "推荐书目A", "snippet": "好书"},
                   {"title": "推荐书目B", "snippet": "也不错"}]
        prompt = (f"[TASK:RECOMMEND]\n"
                  f"Persona (JSON):\n{json.dumps(prof)}\n"
                  f"Web search results (real, JSON):\n{json.dumps(results)}")
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)
        assert len(result) <= 3
        for r in result:
            assert "item" in r
            assert "based_on" in r

    def test_recommend_empty_when_no_results(self, llm):
        prompt = "[TASK:RECOMMEND]\nPersona (JSON):\n{}\nWeb search results (real, JSON):\n[]"
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)
        assert len(result) == 0

    def test_build_wiki(self, llm):
        mems = [{"kind": "event", "content": "去爬山", "id": "m1"},
                {"kind": "preference", "content": "喜欢历史", "id": "m2"}]
        prompt = (f"[TASK:BUILD_WIKI]\n"
                  f"New memories (JSON):\n{json.dumps(mems)}\n"
                  f"Existing wiki pages (JSON):\n[]")
        result = extract_json(llm.chat("", prompt))
        assert isinstance(result, list)
        for page in result:
            assert "title" in page
            assert "body" in page
            assert "tags" in page
            assert "source_ids" in page


# ── Embedder factory + HashingEmbedder ────────────────────────────

class TestEmbedderFactory:
    def test_hashing_default(self):
        emb = get_embedder()
        assert isinstance(emb, HashingEmbedder)
        assert isinstance(emb, Embedder)

    def test_unknown_raises(self, monkeypatch):
        monkeypatch.setitem(config.CONFIG, "embedder", {"backend": "nonexistent"})
        with pytest.raises(ValueError, match="nonexistent"):
            get_embedder()


class TestHashingEmbedder:
    @pytest.fixture
    def emb(self):
        return HashingEmbedder(dim=128)

    def test_returns_correct_dim(self, emb):
        vecs = emb.embed(["hello world"])
        assert len(vecs) == 1
        assert vecs[0].shape == (128,)
        assert vecs[0].dtype == np.float32

    def test_batch(self, emb):
        vecs = emb.embed(["a", "b", "c"])
        assert len(vecs) == 3

    def test_l2_normalized(self, emb):
        vecs = emb.embed(["test string"])
        norm = float(np.linalg.norm(vecs[0]))
        assert abs(norm - 1.0) < 1e-5

    def test_deterministic(self, emb):
        v1 = emb.embed(["same text"])[0]
        v2 = emb.embed(["same text"])[0]
        assert np.allclose(v1, v2)

    def test_different_texts_different_vectors(self, emb):
        v1, v2 = emb.embed(["alpha beta", "gamma delta"])
        assert not np.allclose(v1, v2)

    def test_embed_one(self, emb):
        v = emb.embed_one("hello")
        assert v.shape == (128,)

    def test_empty_string(self, emb):
        v = emb.embed([""])[0]
        assert v.shape == (128,)


# ── ASR factory + StubTranscriber ─────────────────────────────────

class TestASRFactory:
    def test_stub_default(self):
        t = get_transcriber()
        assert isinstance(t, StubTranscriber)
        assert isinstance(t, Transcriber)

    def test_unknown_raises(self, monkeypatch):
        monkeypatch.setitem(config.CONFIG, "asr", {"backend": "nonexistent"})
        with pytest.raises(ValueError, match="nonexistent"):
            get_transcriber()


class TestStubTranscriber:
    def test_returns_segments(self):
        t = StubTranscriber()
        segs = t.transcribe("fake_audio.wav")
        assert isinstance(segs, list)
        assert len(segs) == len(StubTranscriber.SAMPLE)
        for s in segs:
            assert isinstance(s, Segment)

    def test_segment_fields(self):
        t = StubTranscriber()
        segs = t.transcribe("test.wav")
        for s in segs:
            assert s.id
            assert s.source_file == "test.wav"
            assert s.start_sec >= 0
            assert s.end_sec > s.start_sec
            assert s.text
            assert s.speaker == "user"
            assert s.language == "zh"

    def test_txt_input(self, tmp_path):
        f = tmp_path / "recording.txt"
        f.write_text("第一句话\n第二句话\n第三句话", encoding="utf-8")
        t = StubTranscriber()
        segs = t.transcribe(str(f))
        assert len(segs) == 3
        assert segs[0].text == "第一句话"
        assert segs[2].text == "第三句话"
        assert segs[0].source_file == "recording.txt"

    def test_to_tuple(self):
        t = StubTranscriber()
        segs = t.transcribe("x.wav")
        tup = segs[0].to_tuple()
        assert len(tup) == 10
        assert tup[0] == segs[0].id


# ── Speaker factory + TextDiarizer ────────────────────────────────

class TestSpeakerFactory:
    def test_text_default(self):
        d = get_diarizer()
        assert isinstance(d, TextDiarizer)
        assert isinstance(d, Diarizer)


class TestTextDiarizer:
    def test_no_labels_all_user(self):
        utts = [Utterance(text="今天天气好", speaker="", start=0, end=1),
                Utterance(text="我很开心", speaker="", start=1, end=2)]
        d = TextDiarizer()
        result = d.attribute(utts)
        assert all(u.speaker == "user" for u in result)

    def test_labeled_wo_attribution(self):
        utts = [
            Utterance(text="我今天去跑步了", speaker="A", start=0, end=1),
            Utterance(text="我也去了", speaker="A", start=1, end=2),
            Utterance(text="你跑了多远", speaker="B", start=2, end=3),
        ]
        d = TextDiarizer()
        result = d.attribute(utts)
        assert result[0].speaker == "user"
        assert result[1].speaker == "user"

    def test_returns_utterances(self):
        utts = [Utterance(text="测试", speaker="", start=0, end=1)]
        d = TextDiarizer()
        result = d.attribute(utts)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Utterance)


# ── Interface ABC enforcement ─────────────────────────────────────

class TestInterfaceABC:
    def test_llm_abc_methods(self):
        assert hasattr(LLMClient, "chat")
        assert hasattr(LLMClient, "chat_json")

    def test_embedder_abc_methods(self):
        assert hasattr(Embedder, "embed")
        assert hasattr(Embedder, "embed_one")

    def test_transcriber_methods(self):
        assert hasattr(Transcriber, "transcribe")

    def test_diarizer_methods(self):
        assert hasattr(Diarizer, "attribute")

    def test_real_backends_are_subclasses(self):
        assert issubclass(OpenAICompatLLM, LLMClient)
        assert issubclass(AnthropicProxyLLM, LLMClient)
        assert issubclass(OpenAICompatEmbedder, Embedder)
        assert issubclass(HashingEmbedder, Embedder)
        assert issubclass(StubTranscriber, Transcriber)
        assert issubclass(TextDiarizer, Diarizer)
