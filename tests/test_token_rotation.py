"""test_token_rotation.py — v0.10 token 宽限轮换机制单测。"""
from __future__ import annotations

import pytest

from personal_assistant import auth, config, storage


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "token.db")
    return tmp_path / "token.db"


def test_current_token_accepted(db, monkeypatch):
    monkeypatch.setattr(config, "api_token", lambda: "new-token-123")
    assert auth._check("new-token-123") is True
    assert auth._check("wrong") is False


def test_retired_token_accepted_during_grace(db, monkeypatch):
    monkeypatch.setattr(config, "api_token", lambda: "new-token-123")
    monkeypatch.setattr(config, "get", lambda k, d=None: 7 if k == "auth.token_grace_days" else d)
    auth.retire_token("old-token-abc", grace_days=7)
    # 宽限期内：旧 token 仍被接受
    assert auth._check("old-token-abc") is True
    # 无关 token 拒绝
    assert auth._check("unrelated") is False
    info = auth.list_tokens()
    assert len(info["retired"]) == 1
    assert info["retired"][0]["prefix"] == "old-toke"  # 前 8 位


def test_retired_token_expires_after_grace(db, monkeypatch):
    monkeypatch.setattr(config, "api_token", lambda: "new-token-123")
    monkeypatch.setattr(config, "get", lambda k, d=None: 7 if k == "auth.token_grace_days" else d)
    auth.retire_token("old-token-abc", grace_days=0)  # 0 天 = 立即过期
    assert auth._check("old-token-abc") is False


def test_retired_token_stores_hash_not_plaintext(db, monkeypatch):
    monkeypatch.setattr(config, "api_token", lambda: "new-token-123")
    auth.retire_token("secret-token-xyz")
    raw = storage.kv_get("retired_tokens")
    assert raw is not None
    assert "secret-token-xyz" not in raw  # 不存明文
    assert "hash" in raw  # 只存哈希


def test_revoke_token(db):
    auth.retire_token("alpha-token-1")
    auth.retire_token("beta-token-2")
    assert len(auth._retired_tokens()) == 2
    n = auth.revoke_token(prefix="alpha")
    assert n == 1
    assert len(auth._retired_tokens()) == 1
    n2 = auth.revoke_token(all_tokens=True)
    assert n2 == 1
    assert auth._retired_tokens() == []
