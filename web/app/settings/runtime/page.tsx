"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bot, Eye, MonitorUp, Play, RefreshCw, Server, Square } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { BarrageStatus, LLMConfig, RuntimeStatus } from "@/lib/types";

interface Health { status: string; segments: number; memories: number }

export default function RuntimePage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [model, setModel] = useState<RuntimeStatus | null>(null);
  const [barrage, setBarrage] = useState<BarrageStatus | null>(null);
  const [llm, setLlm] = useState<LLMConfig | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const [nextHealth, nextModel, nextBarrage, nextLlm] = await Promise.all([api.health(), api.localModelStatus(), api.barrageStatus(), api.llmSettings()]);
      setHealth(nextHealth); setModel(nextModel); setBarrage(nextBarrage); setLlm(nextLlm);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "运行状态读取失败。"); }
  };
  useEffect(() => { void load(); }, []);

  const perceptionRunning = Boolean(model?.consumers.includes("perception"));
  const run = async (name: string, action: () => Promise<RuntimeStatus>) => {
    setBusy(name); setError("");
    try { setModel(await action()); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "操作失败，请稍后重试。"); }
    finally { setBusy(""); }
  };

  const startModel = async () => {
    if (!window.confirm("启动本地模型会占用本机内存与算力。确认现在启动？")) return;
    await run("model-start", api.startLocalModel);
  };

  const startPerception = async () => {
    setBusy("perception-start"); setError("");
    try { const result = await api.startPerception(); setModel(result.local_model); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "感知启动失败。"); }
    finally { setBusy(""); }
  };

  const stopPerception = async () => {
    setBusy("perception-stop"); setError("");
    try { const result = await api.stopPerception(); setModel(result.local_model); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "感知停止失败。"); }
    finally { setBusy(""); }
  };

  const backendOptions = useMemo(() => {
    const base = ["stub", "openai_compat", "anthropic_proxy", "glm_anthropic", "ollama", "minicpm_o"];
    return llm?.backend && !base.includes(llm.backend) ? [...base, llm.backend] : base;
  }, [llm]);

  const updateBackend = async (backend: string) => {
    setBusy("llm"); setError("");
    try { setLlm(await api.updateLLM({ backend })); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "LLM 后端更新失败。"); }
    finally { setBusy(""); }
  };

  return (
    <div className="settings-page">
      <header className="settings-header"><div><p>SETTINGS / RUNTIME</p><h1>模型与感知</h1><span>四类状态独立显示，控制只影响对应服务。</span></div><button className="control-button" onClick={() => void load()} disabled={Boolean(busy)}><RefreshCw size={15} />刷新状态</button></header>
      {error && <div role="alert" className="settings-alert is-error"><AlertTriangle size={16} />{error}</div>}

      <div className="runtime-grid">
        <StatusPanel icon={Server} title="PA 服务" testId="runtime-pa" state={health?.status || "unknown"} detail={health ? `${health.segments} 段记录 · ${health.memories} 条记忆` : "正在读取"} />
        <StatusPanel icon={Bot} title="本地模型" testId="runtime-model" state={model?.state || "unknown"} detail={model?.error || (model?.running ? "模型进程可用" : "模型进程未运行")}>
          <div className="settings-actions align-left"><button className="control-button is-primary" disabled={Boolean(busy) || Boolean(model?.running)} onClick={() => void startModel()}><Play size={14} />启动模型</button><button className="control-button" disabled={Boolean(busy) || !model?.running} onClick={() => void run("model-stop", api.stopLocalModel)}><Square size={14} />停止模型</button></div>
        </StatusPanel>
        <StatusPanel icon={Eye} title="环境感知" testId="runtime-perception" state={perceptionRunning ? "running" : "stopped"} detail={perceptionRunning ? "感知消费者正在使用本地模型" : "未采集环境感知信息"}>
          <div className="settings-actions align-left"><button className="control-button is-primary" disabled={Boolean(busy) || perceptionRunning} onClick={() => void startPerception()}><Play size={14} />启动感知</button><button className="control-button" disabled={Boolean(busy)} onClick={() => void stopPerception()}><Square size={14} />停止感知</button></div>
        </StatusPanel>
        <StatusPanel icon={MonitorUp} title="桌面浮层" testId="runtime-overlay" state={barrage?.overlay_clients ? "connected" : "disconnected"} detail={`${barrage?.overlay_clients || 0} 个浮层客户端 · ${barrage?.settings.enabled ? "功能已启用" : "功能未启用"}`} />
      </div>

      <section className="settings-section runtime-config">
        <div className="section-title"><div><h2>LLM 后端</h2><p>选择对话推理后端。此处仅保存后端选择，不自动启动本地模型。</p></div><span>{llm?.model || llm?.backend || "正在读取"}</span></div>
        <label className="control-field"><span>当前后端</span><select value={llm?.backend || "stub"} disabled={busy === "llm"} onChange={(event) => void updateBackend(event.target.value)}>{backendOptions.map((backend) => <option key={backend} value={backend}>{backend}</option>)}</select></label>
        {llm?.backend === "minicpm_o" && <div className="settings-alert"><Bot size={16} /><span><strong>MiniCPM-o 为仅本地模式。</strong>所有推理依赖本机模型状态，仅在本机执行。</span></div>}
      </section>

      <section className="settings-section">
        <div className="section-title"><div><h2>模型消费者</h2><p>停止一个消费者不会隐式停止其他仍在使用模型的功能。</p></div></div>
        <div className="consumer-list">{model?.consumers.length ? model.consumers.map((consumer) => <span key={consumer}>{consumer}</span>) : <p className="settings-empty">当前没有模型消费者。</p>}</div>
      </section>
    </div>
  );
}

function StatusPanel({ icon: Icon, title, state, detail, testId, children }: { icon: typeof Server; title: string; state: string; detail: string; testId: string; children?: React.ReactNode }) {
  return <section className="runtime-panel" data-testid={testId}><div className="runtime-panel-head"><Icon size={18} /><span>{title}</span><strong>{state}</strong></div><p>{detail}</p>{children}</section>;
}
