"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Reveal from "@/components/Reveal";
import { LoadingDots, MonoCount, SectionHeader, WhisperLine } from "@/components/ui";
import { api, clearApiToken, getApiToken, setApiToken } from "@/lib/api";
import { LLM_BACKEND_LABELS, pick } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { LLMConfig, LLMUpstreamProbe, LLMUpstreamState, StatusPayload } from "@/lib/types";

/** 上游协议选项：两种协议的完整调用地址后缀不同，标签里直接写清楚省得用户猜 */
const UPSTREAM_PROTOCOLS: Record<string, string> = {
  openai: "OpenAI 兼容（…/chat/completions）",
  anthropic: "Anthropic 兼容（…/v1/messages）",
};

/** 六格计数（局部映射：status 英文键 → 中文） */
const STATUS_LABELS: Record<keyof StatusPayload, string> = {
  segments: "段",
  memories: "记忆",
  events: "日程",
  reminders: "提醒",
  speakers: "说话人",
  profile_version: "画像版本",
};
const STATUS_KEYS = Object.keys(STATUS_LABELS) as (keyof StatusPayload)[];

/** POST /settings/llm 的真实响应（lib 类型按 LLMConfig 标注，运行时附带 applied/note/effective） */
interface LlmSaveResponse {
  backend: string;
  applied?: string[];
  note?: string;
  effective?: Record<string, unknown>;
}

type OpKey = "distill" | "ingest" | "wiki";
type OpPhase = "idle" | "running" | "ok" | "err";
interface OpState {
  phase: OpPhase;
  detail?: string;
}
const OPS: { key: OpKey; label: string; hint: string }[] = [
  { key: "distill", label: "蒸馏记忆", hint: "把段落的余温提炼成画像" },
  { key: "ingest", label: "扫描摄入", hint: "把投喂箱里的薪火收进来" },
  { key: "wiki", label: "重建知识", hint: "重新编织实体之间的菌丝" },
];

type CardNotice = { tone: "moss" | "bloom"; text: string } | null;

/** 三张大卡的入场：与旧 GlassCard 同样的时长与延迟，改经 Reveal 以保证可见性铁律 */
const CARD_TRANSITION = (delay: number) => ({ duration: 0.8, ease: EASE.out, delay });

/** 「系统 · 设置」面板：原 /settings/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function SettingsPanel() {
  // ── 连接 ──
  const [token, setTokenLocal] = useState("");
  const [tokenNotice, setTokenNotice] = useState<CardNotice>(null);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [statusPayload, setStatusPayload] = useState<StatusPayload | null>(null);
  const [probing, setProbing] = useState(false);

  // ── LLM ──
  const [llmReady, setLlmReady] = useState(false);
  const [llmForm, setLlmForm] = useState({ backend: "stub", model: "", baseUrl: "", apiKey: "", maxTokens: "" });
  const [maskedKey, setMaskedKey] = useState("");
  const [effective, setEffective] = useState<Record<string, unknown> | null>(null);
  const [savingLlm, setSavingLlm] = useState(false);
  const [llmNotice, setLlmNotice] = useState<CardNotice>(null);

  // ── LLM 上游（全项目统一：一份配置同步到 PA 与融合记忆系统两侧）──
  const [upReady, setUpReady] = useState(false);
  const [upState, setUpState] = useState<LLMUpstreamState | null>(null);
  const [upForm, setUpForm] = useState({ protocol: "openai", endpoint: "", apiKey: "", model: "", maxTokens: "" });
  const [upNotice, setUpNotice] = useState<CardNotice>(null);
  const [upTesting, setUpTesting] = useState(false);
  const [upSyncing, setUpSyncing] = useState(false);
  const [upProbe, setUpProbe] = useState<LLMUpstreamProbe | null>(null);
  /** 密钥框占位符用：只显示掩码，前端从不持有明文 */
  const upMask = upState?.pa.api_key_masked || upState?.fused.api_key_masked || "";

  // ── 数据管理 ──
  const [ops, setOps] = useState<Record<OpKey, OpState>>({
    distill: { phase: "idle" },
    ingest: { phase: "idle" },
    wiki: { phase: "idle" },
  });

  async function refreshHealth() {
    setProbing(true);
    const [ok, s] = await Promise.all([
      api.health().then(() => true).catch(() => false),
      api.status().catch(() => null),
    ]);
    setHealthOk(ok);
    setStatusPayload(s);
    setProbing(false);
  }

  async function refreshLlm() {
    try {
      const cfg = await api.llmSettings();
      setLlmForm({
        backend: cfg.backend || "stub",
        model: cfg.model || "",
        baseUrl: cfg.base_url || "",
        apiKey: "",
        maxTokens: cfg.max_tokens ? String(cfg.max_tokens) : "",
      });
      setMaskedKey(cfg.api_key_masked || "");
      setEffective(cfg as unknown as Record<string, unknown>);
    } catch {
      setEffective(null);
    } finally {
      setLlmReady(true);
    }
  }

  async function refreshUpstream() {
    try {
      const st = await api.llmUpstream();
      setUpState(st);
      setUpForm((f) => {
        const endpoint = f.endpoint || st.pa.endpoint || st.fused.endpoint || "";
        const proto = endpoint.includes("/v1/messages")
          ? "anthropic"
          : (f.endpoint ? f.protocol : (st.fused.provider === "anthropic" ? "anthropic" : "openai"));
        return {
          protocol: proto,
          endpoint,
          apiKey: "",   // 永不回填明文，留空即沿用服务器已存的那把
          model: f.model || st.pa.model || st.fused.model || "",
          maxTokens: f.maxTokens,
        };
      });
    } catch {
      setUpState(null);
    } finally {
      setUpReady(true);
    }
  }

  function upstreamBody() {
    return {
      protocol: upForm.protocol,
      endpoint: upForm.endpoint.trim(),
      // 留空表示沿用两侧 .env 里已存的密钥，这样只改地址或模型时不必重新粘密钥
      api_key: upForm.apiKey.trim() || undefined,
      model: upForm.model.trim(),
      max_tokens: upForm.maxTokens ? Number(upForm.maxTokens) : undefined,
    };
  }

  async function testUpstream() {
    if (!upForm.endpoint.trim() || !upForm.model.trim()) {
      setUpNotice({ tone: "bloom", text: "先填调用地址与模型" });
      return;
    }
    setUpTesting(true);
    setUpProbe(null);
    setUpNotice(null);
    try {
      const r = await api.testLLMUpstream(upstreamBody());
      setUpProbe(r);
      setUpNotice(r.ok
        ? { tone: "moss", text: `通了，${r.latency_ms ?? "?"} ms` }
        : { tone: "bloom", text: r.error || "不通" });
    } catch (e) {
      setUpNotice({ tone: "bloom", text: e instanceof Error ? e.message : "探测失败" });
    } finally {
      setUpTesting(false);
    }
  }

  async function syncUpstream() {
    if (!upForm.endpoint.trim() || !upForm.model.trim()) {
      setUpNotice({ tone: "bloom", text: "先填调用地址与模型" });
      return;
    }
    setUpSyncing(true);
    setUpNotice(null);
    try {
      const st = await api.applyLLMUpstream(upstreamBody());
      setUpState(st);
      setUpNotice({ tone: "moss", text: "两侧已同步，PA 立即生效" });
      refreshLlm();   // 上面那张「LLM」卡也被改写了，跟着刷新
    } catch (e) {
      setUpNotice({ tone: "bloom", text: e instanceof Error ? e.message : "同步失败" });
    } finally {
      setUpSyncing(false);
    }
  }

  useEffect(() => {
    setTokenLocal(getApiToken());
    refreshHealth();
    refreshLlm();
    refreshUpstream();
  }, []);

  function saveToken() {
    setApiToken(token);
    setTokenNotice({ tone: "moss", text: "令牌已记住" });
    refreshHealth();
  }

  function clearToken() {
    clearApiToken();
    setTokenLocal("");
    setTokenNotice({ tone: "moss", text: "令牌已拂去" });
  }

  async function saveLLM() {
    if (savingLlm) return;
    setSavingLlm(true);
    setLlmNotice(null);
    try {
      const body: Partial<LLMConfig> & { api_key?: string } = { backend: llmForm.backend };
      if (llmForm.model.trim()) body.model = llmForm.model.trim();
      if (llmForm.baseUrl.trim()) body.base_url = llmForm.baseUrl.trim();
      if (llmForm.apiKey.trim()) body.api_key = llmForm.apiKey.trim();
      const mt = Number(llmForm.maxTokens);
      if (Number.isFinite(mt) && mt > 0) body.max_tokens = mt;

      const res = (await api.updateLLM(body)) as unknown as LlmSaveResponse;
      if (res.effective) {
        setEffective(res.effective);
        const mk = res.effective.api_key_masked;
        setMaskedKey(typeof mk === "string" ? mk : "");
      }
      setLlmForm((f) => ({ ...f, apiKey: "" }));
      setLlmNotice({ tone: "moss", text: res.note ? `${res.note}` : "模型配置已更新" });
    } catch {
      setLlmNotice({ tone: "bloom", text: "保存没有抵达——炉火熄了，稍后再试" });
    } finally {
      setSavingLlm(false);
    }
  }

  async function runOp(key: OpKey) {
    if (ops[key].phase === "running") return;
    setOps((o) => ({ ...o, [key]: { phase: "running" } }));
    const res = key === "distill" ? await api.distill() : key === "ingest" ? await api.ingest() : await api.wikiBuild();
    if (res === null) {
      setOps((o) => ({ ...o, [key]: { phase: "err" } }));
      return;
    }
    const r = res as Record<string, unknown>;
    if (typeof r.error === "string" && r.error) {
      setOps((o) => ({ ...o, [key]: { phase: "err", detail: r.error as string } }));
      return;
    }
    if (key === "wiki" && typeof r.returncode === "number" && r.returncode !== 0) {
      setOps((o) => ({ ...o, [key]: { phase: "err", detail: "构建脚本未能完成" } }));
      return;
    }
    let detail: string | undefined;
    if (key === "distill" && typeof r.distilled === "number") detail = `新蒸馏 ${r.distilled} 条`;
    if (key === "wiki" && typeof r.new_pages === "number") {
      detail = `新页 ${r.new_pages} · 扩展 ${typeof r.extended === "number" ? r.extended : 0}`;
    }
    setOps((o) => ({ ...o, [key]: { phase: "ok", detail } }));
    refreshHealth();
  }

  return (
    <div className="space-y-16">
      <WhisperLine>炉火、灯芯与柴房——三处简朴的开关</WhisperLine>

      {/* ── 连接 ───────────────────────────────────────────── */}
      <Reveal as="section" className="glass-card p-6" transition={CARD_TRANSITION(0.05)}>
        <SectionHeader title="连接" subtitle="令牌与后端的呼吸" />
        <div className="flex flex-col gap-6">
          <div>
            <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>
              访问令牌
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                className="input-glow flex-1"
                type="password"
                placeholder="粘贴访问令牌……"
                value={token}
                onChange={(e) => setTokenLocal(e.target.value)}
              />
              <div className="flex gap-3">
                <button className="btn-lumen" onClick={saveToken}>
                  记住令牌
                </button>
                <button className="btn-ghost" onClick={clearToken}>
                  拂去
                </button>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <p className="text-[12px]" style={{ color: "var(--text-weak)" }}>
                令牌只存在于此浏览器的会话里
              </p>
              {tokenNotice && (
                <motion.span
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE.out }}
                  className="text-[12px]"
                  style={{ color: tokenNotice.tone === "moss" ? "var(--mineral-deep)" : "var(--cinnabar-deep)" }}
                >
                  {tokenNotice.text}
                </motion.span>
              )}
            </div>
          </div>

          <div className="pt-6" style={{ borderTop: "1px solid var(--edge)" }}>
            <div className="flex items-center gap-3 mb-4">
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{
                  background: healthOk === null ? "var(--text-weak)" : healthOk ? "var(--mineral)" : "var(--cinnabar)",
                  boxShadow:
                    healthOk === null ? "none" : healthOk ? "0 0 8px var(--min-30)" : "0 0 8px var(--cin-28)",
                }}
              />
              <span className="text-[13px]" style={{ color: "var(--text-dim)" }}>
                {healthOk === null ? "正在探炉火……" : healthOk ? "炉火正旺，后端在低语" : "连不上后端——炉火未点燃"}
              </span>
              <button
                className="text-[12px] ml-auto"
                style={{ color: "var(--indigo)", transition: "opacity 0.5s var(--ease-out)" }}
                onClick={refreshHealth}
                disabled={probing}
              >
                {probing ? "探查中…" : "再探一次"}
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {STATUS_KEYS.map((k, i) => (
                <motion.div
                  key={k}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.05, duration: 0.6, ease: EASE.out }}
                  className="rounded-xl p-3 text-center"
                  style={{ background: "var(--porcelain-1)", border: "1px solid var(--edge)" }}
                >
                  <MonoCount value={statusPayload ? statusPayload[k] : "—"} size={18} />
                  <div className="text-[11px] mt-1" style={{ color: "var(--text-weak)" }}>
                    {STATUS_LABELS[k]}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </Reveal>

      {/* ── LLM ────────────────────────────────────────────── */}
      <Reveal as="section" className="glass-card p-6" transition={CARD_TRANSITION(0.12)}>
        <SectionHeader title="LLM" subtitle="她思考时借用的那盏灯" />
        {!llmReady ? (
          <LoadingDots label="正在读取灯的配置……" />
        ) : (
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>后端</label>
                <select
                  className="input-glow"
                  value={llmForm.backend}
                  onChange={(e) => setLlmForm((f) => ({ ...f, backend: e.target.value }))}
                >
                  {Object.keys(LLM_BACKEND_LABELS).map((k) => (
                    <option key={k} value={k}>
                      {pick(LLM_BACKEND_LABELS, k)}
                    </option>
                  ))}
                  {!LLM_BACKEND_LABELS[llmForm.backend] && (
                    <option value={llmForm.backend}>{llmForm.backend}</option>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>模型</label>
                <input
                  className="input-glow"
                  placeholder="模型名……"
                  value={llmForm.model}
                  onChange={(e) => setLlmForm((f) => ({ ...f, model: e.target.value }))}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>服务地址</label>
              <input
                className="input-glow"
                placeholder="https://……"
                value={llmForm.baseUrl}
                onChange={(e) => setLlmForm((f) => ({ ...f, baseUrl: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>密钥</label>
                <input
                  className="input-glow"
                  type="password"
                  placeholder={maskedKey ? `当前 ${maskedKey}（留空保持不变）` : "留空保持不变"}
                  value={llmForm.apiKey}
                  onChange={(e) => setLlmForm((f) => ({ ...f, apiKey: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>最大生成长度</label>
                <input
                  className="input-glow"
                  type="number"
                  min={1}
                  placeholder="如 2048"
                  value={llmForm.maxTokens}
                  onChange={(e) => setLlmForm((f) => ({ ...f, maxTokens: e.target.value }))}
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button className="btn-lumen" onClick={saveLLM} disabled={savingLlm}>
                {savingLlm ? "保存中…" : "保存"}
              </button>
              {llmNotice && (
                <motion.span
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE.out }}
                  className="text-[13px] px-3 py-1 rounded-full"
                  style={{
                    background: llmNotice.tone === "moss" ? "var(--min-10)" : "var(--cin-10)",
                    color: llmNotice.tone === "moss" ? "var(--mineral-deep)" : "var(--cinnabar-deep)",
                  }}
                >
                  {llmNotice.text}
                </motion.span>
              )}
            </div>

            {effective && (
              <div>
                <div className="text-xs mb-2" style={{ color: "var(--text-weak)" }}>
                  生效中的配置
                </div>
                <pre
                  className="text-[12px] p-4 rounded-xl overflow-auto"
                  style={{
                    background: "var(--porcelain-1)",
                    border: "1px solid var(--edge)",
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-dim)",
                    lineHeight: 1.7,
                  }}
                >
                  {JSON.stringify(effective, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Reveal>

      {/* ── LLM 上游 · 全项目统一 ───────────────────────────── */}
      <Reveal as="section" className="glass-card p-6" transition={CARD_TRANSITION(0.16)}>
        <SectionHeader title="LLM 上游 · 全项目" subtitle="一盏灯，照两处：PA 与融合记忆系统" />
        {!upReady ? (
          <LoadingDots label="正在读取两侧的配置……" />
        ) : (
          <div className="flex flex-col gap-5">
            <p className="text-[12px]" style={{ color: "var(--text-weak)", lineHeight: 1.8 }}>
              这里填一次，同时写进两侧：融合记忆系统根 .env 的 INFO_LLM_* 与 MOMENT_LLM_*，
              以及 PA .env 的 PA_LLM_*。两侧 base_url 语义不同，后端自动换算——融合侧存完整调用地址，
              PA 侧存去掉协议后缀的 base。PA 立即生效，融合侧下次跑脚本时生效。
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>协议</label>
                <select
                  className="input-glow"
                  value={upForm.protocol}
                  onChange={(e) => setUpForm((f) => ({ ...f, protocol: e.target.value }))}
                >
                  {Object.keys(UPSTREAM_PROTOCOLS).map((k) => (
                    <option key={k} value={k}>{UPSTREAM_PROTOCOLS[k]}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>模型</label>
                <input
                  className="input-glow"
                  placeholder="如 glm-4.6 / deepseek-chat"
                  value={upForm.model}
                  onChange={(e) => setUpForm((f) => ({ ...f, model: e.target.value }))}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>完整调用地址</label>
              <input
                className="input-glow"
                placeholder={upForm.protocol === "anthropic"
                  ? "https://……/v1/messages"
                  : "https://……/v1/chat/completions"}
                value={upForm.endpoint}
                onChange={(e) => setUpForm((f) => ({ ...f, endpoint: e.target.value }))}
              />
              <div className="text-[11px] mt-2" style={{ color: "var(--text-weak)" }}>
                填到能直接 POST 的那一层；只填根路径也会按协议自动补全。
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>密钥</label>
                <input
                  className="input-glow"
                  type="password"
                  placeholder={upMask ? `当前 ${upMask}（留空保持不变）` : "留空则沿用已存密钥"}
                  value={upForm.apiKey}
                  onChange={(e) => setUpForm((f) => ({ ...f, apiKey: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>最大生成长度（可选）</label>
                <input
                  className="input-glow"
                  type="number"
                  min={1}
                  placeholder="留空沿用现有"
                  value={upForm.maxTokens}
                  onChange={(e) => setUpForm((f) => ({ ...f, maxTokens: e.target.value }))}
                />
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <button className="btn-ghost" onClick={testUpstream} disabled={upTesting}>
                {upTesting ? "探测中…" : "测试连通"}
              </button>
              <button className="btn-lumen" onClick={syncUpstream} disabled={upSyncing}>
                {upSyncing ? "同步中…" : "一键同步到全项目"}
              </button>
              {upNotice && (
                <motion.span
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE.out }}
                  className="text-[13px] px-3 py-1 rounded-full"
                  style={{
                    background: upNotice.tone === "moss" ? "var(--min-10)" : "var(--cin-10)",
                    color: upNotice.tone === "moss" ? "var(--mineral-deep)" : "var(--cinnabar-deep)",
                  }}
                >
                  {upNotice.text}
                </motion.span>
              )}
            </div>

            {upProbe && (
              <div
                className="text-[12px] p-4 rounded-xl"
                style={{
                  background: "var(--porcelain-1)",
                  border: "1px solid var(--edge)",
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-dim)",
                  lineHeight: 1.8,
                }}
              >
                <div>
                  探测{upProbe.ok ? "成功" : "失败"} · {upProbe.protocol} · HTTP {upProbe.status ?? "—"} · {upProbe.latency_ms ?? "—"} ms
                </div>
                <div className="break-all">实际请求 {upProbe.url}</div>
                {upProbe.reply_head && <div>回复开头 {upProbe.reply_head}</div>}
                {upProbe.detail && (
                  <div className="break-all" style={{ color: "var(--cinnabar-deep)" }}>{upProbe.detail}</div>
                )}
              </div>
            )}

            {upState && (
              <div>
                <div className="text-xs mb-2" style={{ color: "var(--text-weak)" }}>
                  两侧现状 · {upState.note}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {([
                    {
                      name: "PA（本机 .env）",
                      s: upState.pa,
                      head: `backend = ${upState.pa.backend || "未设"}`
                        + (upState.pa.from_env ? "" : "　（来自 default.json，非 .env）"),
                    },
                    { name: "融合记忆系统（项目根 .env）", s: upState.fused, head: `provider = ${upState.fused.provider || "未设"}` },
                  ] as const).map((side) => (
                    <div
                      key={side.name}
                      className="text-[12px] p-4 rounded-xl"
                      style={{
                        background: "var(--porcelain-1)",
                        border: "1px solid var(--edge)",
                        fontFamily: "var(--font-mono)",
                        color: "var(--text-dim)",
                        lineHeight: 1.8,
                      }}
                    >
                      <div style={{ color: "var(--text-weak)" }}>{side.name}</div>
                      <div>{side.head}</div>
                      <div className="break-all">地址 {side.s.endpoint || "（空）"}</div>
                      <div>模型 {side.s.model || "（空）"}</div>
                      <div>密钥 {side.s.api_key_masked || "（空）"}</div>
                      <div className="break-all" style={{ color: "var(--text-weak)" }}>{side.s.env_file}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Reveal>

      {/* ── 数据管理 ────────────────────────────────────────── */}
      <Reveal as="section" className="glass-card p-6" transition={CARD_TRANSITION(0.2)}>
        <SectionHeader title="数据管理" subtitle="三件粗活：蒸馏、摄入、重建" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {OPS.map((op) => {
            const st = ops[op.key];
            return (
              <div key={op.key} className="flex flex-col gap-3">
                <button className="btn-ghost" onClick={() => runOp(op.key)} disabled={st.phase === "running"}>
                  {op.label}
                </button>
                <div className="text-[11px]" style={{ color: "var(--text-weak)" }}>
                  {op.hint}
                </div>
                <div className="min-h-[26px]">
                  {st.phase === "running" && <LoadingDots label="正在……" />}
                  {st.phase === "ok" && (
                    <motion.p
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.6, ease: EASE.out }}
                      className="text-[13px]"
                      style={{ color: "var(--mineral-deep)" }}
                    >
                      完成{st.detail ? ` · ${st.detail}` : ""}
                    </motion.p>
                  )}
                  {st.phase === "err" && (
                    <motion.p
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.6, ease: EASE.out }}
                      className="text-[13px]"
                      style={{ color: "var(--cinnabar-deep)" }}
                    >
                      炉火熄了{st.detail ? ` · ${st.detail}` : ""}
                    </motion.p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Reveal>
    </div>
  );
}
