from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE_ROOT = ROOT / "scripts" / "xiaozhi-esp32"
FIRMWARE_MAIN = FIRMWARE_ROOT / "main"


def _source(name: str) -> str:
    return (FIRMWARE_MAIN / name).read_text(encoding="utf-8")


def test_ota_preserves_local_websocket_credentials() -> None:
    source = _source("ota.cc")

    assert 'strlen(CONFIG_PA_SERVER_URL) > 0' in source
    assert 'strcmp(key, "url") == 0' in source
    assert 'strcmp(key, "token") == 0' in source
    assert "ShouldPreserveLocalWebsocketSetting(item->string)" in source


def test_background_audio_prefers_nvs_token_with_kconfig_fallback() -> None:
    source = _source("application.cc")

    assert 'Settings ws_read("websocket", false);' in source
    assert 'ws_read.GetString("token", CONFIG_PA_SERVER_TOKEN)' in source


def test_trimmed_firmware_never_writes_token_to_nvs() -> None:
    """录音上传专用固件（v0.12 裁剪后）：token 只走"NVS 读 + Kconfig 回退"，
    启动绝不把凭据写回 NVS——旧对话协议的播种写逻辑已随协议模块删除。"""
    source = _source("application.cc")

    assert 'GetString("token", CONFIG_PA_SERVER_TOKEN)' in source
    assert 'SetString("token"' not in source


def test_background_audio_uses_bearer_header_without_logging_token() -> None:
    source = (
        FIRMWARE_ROOT / "components" / "background_audio" / "background_audio.cpp"
    ).read_text(encoding="utf-8")

    assert 'ws/audio?token=' not in source
    assert '"Authorization: Bearer %s\\r\\n"' in source
    assert "cfg.headers = g_ctx.ws_headers" in source
    assert 'ESP_LOGI(TAG, "初始化完成: %s' not in source
    assert '鉴权=%s' in source


def test_ota_credential_guard_precedes_type_branch() -> None:
    """url/token 保护必须先按 key 判断再按类型处理：
    异常 OTA 把凭据表示为数字时也不能覆盖本地配置（continue 在类型分支之前）。"""
    source = _source("ota.cc")

    guard = "if (ShouldPreserveLocalWebsocketSetting(item->string)) {"
    assert guard in source
    after = source.split(guard, 1)[1]
    assert "continue;" in after
    preserved = after.split("continue;", 1)[0]
    assert "SetString" not in preserved
    assert "SetInt" not in preserved


def test_background_audio_rejects_truncated_bearer_header() -> None:
    """token 过长时不得带截断凭据连接：长度检查 + 放弃 header + 告警。"""
    source = (
        FIRMWARE_ROOT / "components" / "background_audio" / "background_audio.cpp"
    ).read_text(encoding="utf-8")

    assert "int needed = snprintf(NULL, 0" in source
    assert "g_ctx.ws_headers[0] = '\\0';" in source
    assert "ws token too long" in source
    assert "sizeof(g_ctx.ws_headers)" in source
