"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Monitor, RefreshCw, Save, Send } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { BarrageSettings, BarrageStatus } from "@/lib/types";

export default function BarragePage() {
  const [settings, setSettings] = useState<BarrageSettings | null>(null);
  const [status, setStatus] = useState<BarrageStatus | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState<{ id: string; state: string } | null>(null);

  const load = async () => {
    setError("");
    try {
      const [nextSettings, nextStatus] = await Promise.all([api.barrageSettings(), api.barrageStatus()]);
      setSettings(nextSettings); setStatus(nextStatus);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "弹幕设置读取失败。"); }
  };
  useEffect(() => { void load(); }, []);

  const save = async () => {
    if (!settings) return;
    setBusy("save"); setError("");
    try { setSettings(await api.updateBarrageSettings(settings)); setStatus(await api.barrageStatus()); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "弹幕设置保存失败。"); }
    finally { setBusy(""); }
  };

  const test = async () => {
    setBusy("test"); setError(""); setTestResult(null);
    try { const event = await api.testBarrage(); setTestResult({ id: event.id, state: "后端已接受" }); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "测试弹幕发送失败。"); }
    finally { setBusy(""); }
  };

  if (!settings) return <div className="settings-page"><p className="settings-loading">正在读取桌面弹幕设置…</p>{error && <p role="alert" className="settings-alert is-error">{error}</p>}</div>;

  return (
    <div className="settings-page">
      <header className="settings-header"><div><p>SETTINGS / BARRAGE</p><h1>桌面弹幕</h1><span>浮层投递由后端决定，安静、暂停或关闭时测试可能被拒绝。</span></div><div className="settings-actions"><button className="control-button" onClick={() => void load()} disabled={Boolean(busy)}><RefreshCw size={15} />重新加载</button><button className="control-button is-primary" onClick={() => void save()} disabled={Boolean(busy)}><Save size={15} />{busy === "save" ? "保存中…" : "保存设置"}</button></div></header>
      {error && <div role="alert" className="settings-alert is-error"><AlertTriangle size={16} />{error}</div>}

      <div className="barrage-layout">
        <section className="settings-section">
          <div className="section-title"><div><h2>投递开关</h2><p>暂停截止时间为空表示不暂停。</p></div></div>
          <div className="toggle-list">
            <Toggle label="启用桌面弹幕" checked={settings.enabled} onChange={(enabled) => setSettings({ ...settings, enabled })} />
            <Toggle label="安静模式" checked={settings.quiet_mode} onChange={(quiet_mode) => setSettings({ ...settings, quiet_mode })} />
          </div>
          <label className="control-field"><span>暂停至</span><input type="datetime-local" value={settings.paused_until ? settings.paused_until.slice(0, 16) : ""} onChange={(event) => setSettings({ ...settings, paused_until: event.target.value })} /></label>
        </section>

        <section className="settings-section">
          <div className="section-title"><div><h2>显示位置</h2><p>选择屏幕、位置和配色主题。</p></div></div>
          <div className="field-grid three">
            <label className="control-field"><span>位置</span><select value={settings.position} onChange={(event) => setSettings({ ...settings, position: event.target.value as BarrageSettings["position"] })}><option value="top">顶部</option><option value="center">中部</option><option value="bottom">底部</option></select></label>
            <label className="control-field"><span>主题</span><select value={settings.theme} onChange={(event) => setSettings({ ...settings, theme: event.target.value as BarrageSettings["theme"] })}><option value="contrast">高对比</option><option value="light">浅色</option><option value="dark">深色</option></select></label>
            <label className="control-field"><span>显示器 ID</span><input value={settings.display_id} onChange={(event) => setSettings({ ...settings, display_id: event.target.value })} /></label>
          </div>
        </section>

        <section className="settings-section barrage-ranges">
          <div className="section-title"><div><h2>视觉参数</h2><p>尺寸、透明度和停留时长由浮层客户端按设置渲染。</p></div></div>
          <label className="control-field range-field"><span>字号 <b>{settings.font_size}px</b></span><input aria-label="弹幕字号" type="range" min="14" max="72" value={settings.font_size} onChange={(event) => setSettings({ ...settings, font_size: Number(event.target.value) })} /><input aria-label="弹幕字号数值" type="number" min="14" max="72" value={settings.font_size} onChange={(event) => setSettings({ ...settings, font_size: Number(event.target.value) })} /></label>
          <label className="control-field range-field"><span>透明度 <b>{Math.round(settings.opacity * 100)}%</b></span><input aria-label="弹幕透明度" type="range" min="0.1" max="1" step="0.05" value={settings.opacity} onChange={(event) => setSettings({ ...settings, opacity: Number(event.target.value) })} /></label>
          <label className="control-field range-field"><span>停留时长 <b>{settings.duration_seconds}s</b></span><input aria-label="弹幕时长" type="range" min="2" max="30" value={settings.duration_seconds} onChange={(event) => setSettings({ ...settings, duration_seconds: Number(event.target.value) })} /></label>
        </section>

        <section className="settings-section barrage-test">
          <div className="section-title"><div><h2>后端投递测试</h2><p>这里不做本地假预览，只显示后端返回的事件或错误。</p></div><Monitor size={18} /></div>
          <dl><div><dt>浮层客户端</dt><dd>{status?.overlay_clients ?? 0}</dd></div><div><dt>后端暂停状态</dt><dd>{status?.paused ? "已暂停" : "未暂停"}</dd></div></dl>
          <button className="control-button is-primary" onClick={() => void test()} disabled={Boolean(busy)}><Send size={15} />{busy === "test" ? "等待后端…" : "发送测试弹幕"}</button>
          {testResult && <div className="test-result" role="status"><strong>{testResult.state}</strong><span>事件 ID</span><code>{testResult.id}</code></div>}
        </section>
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="toggle-row"><span>{label}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><i aria-hidden="true" /></label>;
}
