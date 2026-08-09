"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Eye, Plus, RefreshCw, Save, X } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type {
  AssistantPersonality,
  AssistantPersonalityInput,
  PersonalityBarrageStyle,
  PersonalityInitiative,
  PersonalityPreview,
  PersonalityReplyLength,
  PersonalityPreset,
} from "@/lib/types";

const presets: Array<{ id: PersonalityPreset; label: string; note: string }> = [
  { id: "gentle", label: "温和陪伴", note: "温和、平衡、克制" },
  { id: "rational", label: "理性克制", note: "直接、低幽默、少打扰" },
  { id: "lively", label: "轻快活泼", note: "简短、主动、有幽默感" },
  { id: "coach", label: "行动教练", note: "明确、短促、推动行动" },
];

const presetValues: Record<PersonalityPreset, Omit<AssistantPersonalityInput, "preset_id">> = {
  gentle: { name: "PA", user_address: "你", directness: 2, humor: 2, initiative: "balanced", reply_length: "balanced", barrage_style: "restrained", taboos: [], custom_instruction: "" },
  rational: { name: "PA", user_address: "你", directness: 4, humor: 1, initiative: "restrained", reply_length: "balanced", barrage_style: "restrained", taboos: [], custom_instruction: "" },
  lively: { name: "PA", user_address: "你", directness: 3, humor: 5, initiative: "active", reply_length: "short", barrage_style: "light", taboos: [], custom_instruction: "" },
  coach: { name: "PA", user_address: "你", directness: 5, humor: 2, initiative: "balanced", reply_length: "short", barrage_style: "coach", taboos: [], custom_instruction: "" },
};

const initiativeOptions: Array<[PersonalityInitiative, string]> = [
  ["quiet", "安静"], ["restrained", "克制"], ["balanced", "平衡"], ["active", "主动"], ["companion", "陪伴"],
];
const replyOptions: Array<[PersonalityReplyLength, string]> = [["short", "简短"], ["balanced", "适中"], ["detailed", "详细"]];
const barrageOptions: Array<[PersonalityBarrageStyle, string]> = [["restrained", "克制"], ["light", "轻快"], ["coach", "教练"], ["game", "游戏"]];

function inputOf(value: AssistantPersonality): AssistantPersonalityInput {
  return {
    preset_id: value.preset_id,
    name: value.name,
    user_address: value.user_address,
    directness: value.directness,
    humor: value.humor,
    initiative: value.initiative,
    reply_length: value.reply_length,
    barrage_style: value.barrage_style,
    taboos: value.taboos,
    custom_instruction: value.custom_instruction,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "操作失败，请稍后重试。";
}

export default function PersonalityPage() {
  const [saved, setSaved] = useState<AssistantPersonality | null>(null);
  const [draft, setDraft] = useState<AssistantPersonalityInput | null>(null);
  const [preview, setPreview] = useState<PersonalityPreview | null>(null);
  const [tabooDraft, setTabooDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const value = await api.assistantPersonality();
      const input = inputOf(value);
      setSaved(value);
      setDraft(input);
      try {
        setPreview(await api.previewAssistantPersonality(input));
      } catch (reason) {
        setError(errorMessage(reason));
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const dirty = useMemo(() => {
    if (!saved || !draft) return false;
    return JSON.stringify(inputOf(saved)) !== JSON.stringify(draft);
  }, [draft, saved]);

  const applyPreset = (preset: PersonalityPreset) => {
    setDraft({ preset_id: preset, ...presetValues[preset] });
    setError("");
  };

  const updatePreview = async () => {
    if (!draft) return;
    setPreviewing(true);
    setError("");
    try {
      setPreview(await api.previewAssistantPersonality(draft));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPreviewing(false);
    }
  };

  const save = async () => {
    if (!draft || !saved) return;
    setSaving(true);
    setError("");
    try {
      const value = await api.updateAssistantPersonality({ ...draft, expected_version: saved.version });
      setSaved(value);
      setDraft(inputOf(value));
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError("性格配置已在其他页面更新，请重新加载后合并修改。");
      } else {
        setError(errorMessage(reason));
      }
    } finally {
      setSaving(false);
    }
  };

  const addTaboo = () => {
    if (!draft) return;
    const value = tabooDraft.trim();
    if (!value || draft.taboos.includes(value) || draft.taboos.length >= 30) return;
    setDraft({ ...draft, preset_id: "custom", taboos: [...draft.taboos, value] });
    setTabooDraft("");
  };

  if (loading || !draft || !saved) {
    return <div className="settings-page"><p className="settings-loading">正在读取助手性格…</p>{error && <p role="alert" className="settings-alert is-error">{error}</p>}</div>;
  }

  return (
    <div className="settings-page">
      <header className="settings-header">
        <div><p>ASSISTANT / PERSONALITY</p><h1>性格工作室</h1><span>只定义助手如何表达，不修改“我的画像”。</span></div>
        <div className="settings-actions">
          {dirty && <span className="settings-dirty">有未保存修改</span>}
          <button className="control-button" onClick={() => void load()} disabled={loading || saving}><RefreshCw size={15} />重新加载</button>
          <button className="control-button is-primary" onClick={() => void save()} disabled={!dirty || saving}><Save size={15} />{saving ? "保存中…" : "保存性格"}</button>
        </div>
      </header>

      {error && <div role="alert" className="settings-alert is-error"><AlertTriangle size={16} />{error}</div>}

      <div className="settings-columns personality-layout">
        <section className="settings-section">
          <div className="section-title"><div><h2>预设与称呼</h2><p>预设会覆盖当前未保存字段，选择本身不会写入后端。</p></div><span>v{saved.version}</span></div>
          <div className="preset-grid">
            {presets.map((preset) => (
              <button key={preset.id} type="button" aria-label={preset.label} className={draft.preset_id === preset.id ? "preset-option is-active" : "preset-option"} onClick={() => applyPreset(preset.id)} aria-pressed={draft.preset_id === preset.id}>
                <strong>{preset.label}</strong><span aria-hidden="true">{preset.note}</span>
              </button>
            ))}
          </div>
          <div className="field-grid two">
            <label className="control-field"><span>助手名字</span><input maxLength={20} value={draft.name} onChange={(event) => setDraft({ ...draft, preset_id: "custom", name: event.target.value })} /></label>
            <label className="control-field"><span>对你的称呼</span><input maxLength={20} value={draft.user_address} onChange={(event) => setDraft({ ...draft, preset_id: "custom", user_address: event.target.value })} /></label>
          </div>

          <div className="range-grid">
            <label className="control-field range-field"><span>直接程度 <b>{draft.directness}/5</b></span><input aria-label="直接程度" type="range" min="1" max="5" value={draft.directness} onChange={(event) => setDraft({ ...draft, preset_id: "custom", directness: Number(event.target.value) })} /></label>
            <label className="control-field range-field"><span>幽默程度 <b>{draft.humor}/5</b></span><input aria-label="幽默程度" type="range" min="1" max="5" value={draft.humor} onChange={(event) => setDraft({ ...draft, preset_id: "custom", humor: Number(event.target.value) })} /></label>
          </div>

          <Segmented label="主动程度" value={draft.initiative} options={initiativeOptions} onChange={(initiative) => setDraft({ ...draft, preset_id: "custom", initiative })} />
          <Segmented label="回复长度" value={draft.reply_length} options={replyOptions} onChange={(reply_length) => setDraft({ ...draft, preset_id: "custom", reply_length })} />
          <Segmented label="弹幕风格" value={draft.barrage_style} options={barrageOptions} onChange={(barrage_style) => setDraft({ ...draft, preset_id: "custom", barrage_style })} />
        </section>

        <div className="settings-stack">
          <section className="settings-section">
            <div className="section-title"><div><h2>表达边界</h2><p>禁忌最多 30 条，每条不超过 80 字。</p></div><span>{draft.taboos.length}/30</span></div>
            <div className="tag-editor">
              <label className="control-field"><span>新增禁忌</span><div className="inline-input"><input value={tabooDraft} maxLength={80} onChange={(event) => setTabooDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addTaboo(); } }} /><button type="button" aria-label="添加禁忌" onClick={addTaboo} disabled={!tabooDraft.trim() || draft.taboos.length >= 30}><Plus size={16} /></button></div></label>
              <div className="tag-list">{draft.taboos.map((taboo) => <span key={taboo}>{taboo}<button type="button" aria-label={`删除禁忌：${taboo}`} onClick={() => setDraft({ ...draft, preset_id: "custom", taboos: draft.taboos.filter((item) => item !== taboo) })}><X size={12} /></button></span>)}</div>
            </div>
            <label className="control-field"><span>补充指令</span><textarea maxLength={1000} value={draft.custom_instruction} onChange={(event) => setDraft({ ...draft, preset_id: "custom", custom_instruction: event.target.value })} /><small>{draft.custom_instruction.length}/1000</small></label>
          </section>

          <section className="settings-section preview-section">
            <div className="section-title"><div><h2>后端确定性预览</h2><p>使用当前未保存且已通过后端校验的字段生成。</p></div><button className="control-button" onClick={() => void updatePreview()} disabled={previewing}><Eye size={15} />{previewing ? "更新中…" : "更新预览"}</button></div>
            <div className="preview-list">
              <PreviewRow label="聊天回应" text={preview?.chat} />
              <PreviewRow label="定时提醒" text={preview?.reminder} />
              <PreviewRow label="感知提示" text={preview?.perception} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: Array<[T, string]>; onChange: (value: T) => void }) {
  return <fieldset className="segmented-field"><legend>{label}</legend><div>{options.map(([key, text]) => <button key={key} type="button" aria-pressed={value === key} className={value === key ? "is-active" : ""} onClick={() => onChange(key)}>{text}</button>)}</div></fieldset>;
}

function PreviewRow({ label, text }: { label: string; text?: string }) {
  return <article><span>{label}</span><p>{text || "等待预览"}</p></article>;
}
