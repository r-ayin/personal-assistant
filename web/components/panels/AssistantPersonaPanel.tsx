"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";
import { LoadingDots, SectionHeader, Tag, WhisperLine } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import {
  INITIATIVE_LABELS,
  PRESET_LABELS,
  REPLY_LENGTH_LABELS,
  localizeDisplayText,
  pick,
} from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type {
  AssistantPersonality,
  AssistantPersonalityInput,
  PersonalityInitiative,
  PersonalityPreview,
  PersonalityReplyLength,
  ProfileDimension,
  ProfileResponse,
  ProfileValue,
} from "@/lib/types";

/** 人格表单：契约字段（barrage_style 本页不暴露编辑，载入时保留原值随保存透传） */
type PersonaFormState = AssistantPersonalityInput;

/** 画像九维（局部映射：数据层英文键 → 中文） */
const DIM_LABELS: Record<ProfileDimension, string> = {
  personality: "个性",
  values: "价值观",
  goals: "目标",
  habits: "习惯",
  skills: "技能",
  knowledge: "知识",
  thinking_patterns: "思维模式",
  preferences: "偏好",
  affective_baseline: "情感基线",
};
const DIMENSIONS = Object.keys(DIM_LABELS) as ProfileDimension[];

/** 反馈动作（局部映射） */
const ACTION_LABELS: Record<"add" | "suppress", string> = { add: "补充", suppress: "修正" };

/** 试听三句（局部映射） */
const PREVIEW_LABELS: Record<keyof PersonalityPreview, string> = {
  chat: "对话",
  reminder: "提醒",
  perception: "感知",
};

/** 预设基线（点选预设 chips 时套用；随后手动微调即落入「自定义」） */
const PRESET_DEFAULTS: Record<string, Partial<PersonaFormState>> = {
  gentle: { directness: 2, humor: 2, initiative: "balanced", reply_length: "balanced", barrage_style: "restrained" },
  rational: { directness: 4, humor: 1, initiative: "restrained", reply_length: "balanced", barrage_style: "restrained" },
  lively: { directness: 3, humor: 5, initiative: "active", reply_length: "short", barrage_style: "light" },
  coach: { directness: 5, humor: 2, initiative: "balanced", reply_length: "short", barrage_style: "coach" },
};

function toForm(p: AssistantPersonality): PersonaFormState {
  const raw = p as unknown as Record<string, unknown>;
  return {
    preset_id: p.preset_id,
    name: p.name || "PA",
    user_address: p.user_address || "你",
    directness: p.directness,
    humor: p.humor,
    initiative: p.initiative,
    reply_length: p.reply_length,
    barrage_style: (["restrained", "light", "coach", "game"] as const).includes(raw.barrage_style as never)
      ? (raw.barrage_style as PersonaFormState["barrage_style"])
      : "restrained",
    taboos: Array.isArray(p.taboos) ? p.taboos : [],
    custom_instruction: p.custom_instruction || "",
  };
}

function formatProfileValue(v: ProfileValue | undefined): string {
  if (v === null || v === undefined || v === "") return "——";
  if (Array.isArray(v)) return v.length ? localizeDisplayText(v.join("、")) : "——";
  if (typeof v === "boolean") return v ? "是" : "否";
  return localizeDisplayText(String(v));
}

type Notice = { tone: "moss" | "ember" | "bloom"; text: string };
const NOTICE_COLORS: Record<Notice["tone"], [string, string]> = {
  moss: ["var(--min-10)", "var(--mineral-deep)"],
  ember: ["var(--och-10)", "var(--ochre-deep)"],
  bloom: ["var(--cin-10)", "var(--cinnabar-deep)"],
};

/** 两张大卡的入场：与旧 GlassCard 同样的时长与延迟，改经 Reveal 以保证可见性铁律 */
const cardTransition = (delay: number) => ({ duration: 0.8, ease: EASE.out, delay });

/** 「系统 · 助手人格」面板：原 /persona/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function AssistantPersonaPanel() {
  // ── 助手人格 ──
  const [form, setForm] = useState<PersonaFormState | null>(null);
  const [version, setVersion] = useState(0);
  const [personaReady, setPersonaReady] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PersonalityPreview | null>(null);
  const [tabooInput, setTabooInput] = useState("");

  // ── 用户画像 ──
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [profileReady, setProfileReady] = useState(false);
  const [draft, setDraft] = useState<{ dimension: ProfileDimension; action: "add" | "suppress" } | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [draftEvidence, setDraftEvidence] = useState("");
  const [draftBusy, setDraftBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function reloadPersonality() {
    try {
      const p = await api.assistantPersonality();
      setForm(toForm(p));
      setVersion(p.version);
    } catch {
      setForm(null);
    } finally {
      setPersonaReady(true);
    }
  }

  async function reloadProfile() {
    try {
      setProfile(await api.profile());
    } catch {
      setProfile(null);
    } finally {
      setProfileReady(true);
    }
  }

  useEffect(() => {
    reloadPersonality();
    reloadProfile();
  }, []);

  /** 手动微调任何字段 → 预设自动落入「自定义」，旧试听作废 */
  function patchForm(patch: Partial<PersonaFormState>) {
    setForm((f) => (f ? { ...f, ...patch, preset_id: "custom" } : f));
    setPreview(null);
  }

  function choosePreset(id: string) {
    setForm((f) =>
      f ? { ...f, preset_id: id as PersonaFormState["preset_id"], ...(PRESET_DEFAULTS[id] || {}) } : f,
    );
    setPreview(null);
  }

  function addTaboo() {
    const t = tabooInput.trim();
    setTabooInput("");
    if (!t || !form || form.taboos.includes(t) || form.taboos.length >= 30) return;
    patchForm({ taboos: [...form.taboos, t] });
  }

  async function handlePreview() {
    if (!form || previewing) return;
    setPreviewing(true);
    setNotice(null);
    try {
      setPreview(await api.previewAssistantPersonality(form));
    } catch {
      setNotice({ tone: "bloom", text: "试听没有声响——炉火熄了，稍后再试" });
    } finally {
      setPreviewing(false);
    }
  }

  async function handleSave() {
    if (!form || saving) return;
    setSaving(true);
    setNotice(null);
    try {
      const saved = await api.updateAssistantPersonality({ ...form, expected_version: version });
      setForm(toForm(saved));
      setVersion(saved.version);
      setNotice({ tone: "moss", text: "人格已更新" });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setNotice({ tone: "ember", text: "档案在别处被改写，已为你重新拉取" });
        await reloadPersonality();
      } else {
        setNotice({ tone: "bloom", text: "保存失败——炉火熄了，稍后再试" });
      }
    } finally {
      setSaving(false);
    }
  }

  function openDraft(dimension: ProfileDimension, action: "add" | "suppress") {
    setDraft({ dimension, action });
    setDraftValue("");
    setDraftEvidence("");
  }

  async function submitFeedback() {
    if (!draft || !draftValue.trim() || draftBusy) return;
    setDraftBusy(true);
    try {
      await api.addProfileFeedback({
        dimension: draft.dimension,
        value: draftValue.trim(),
        action: draft.action,
        evidence_kind: "user_statement",
        evidence: draftEvidence.trim() || "用户亲口所述",
      });
      setDraft(null);
      setDraftValue("");
      setDraftEvidence("");
      await reloadProfile();
    } catch {
      setNotice({ tone: "bloom", text: "反馈没有抵达——稍后再试" });
    } finally {
      setDraftBusy(false);
    }
  }

  async function removeFeedback(id: string) {
    if (deletingId) return;
    setDeletingId(id);
    try {
      await api.deleteProfileFeedback(id);
      await reloadProfile();
    } catch {
      setNotice({ tone: "bloom", text: "删除失败——稍后再试" });
    } finally {
      setDeletingId(null);
    }
  }

  const formValid = !!form && form.name.trim().length > 0 && form.user_address.trim().length > 0;

  return (
    <>
      {/* 页面私有样式：暖金滑杆 */}
      <style>{`
        .persona-range { -webkit-appearance: none; appearance: none; height: 4px; border-radius: 999px;
          background: var(--ind-16); outline: none; cursor: pointer; }
        .persona-range::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px;
          border-radius: 50%; background: var(--indigo); border: 2px solid var(--porcelain-2);
          box-shadow: 0 0 8px var(--ind-40); transition: transform 0.5s var(--ease-out); }
        .persona-range::-webkit-slider-thumb:hover { transform: scale(1.15); }
        .persona-range::-moz-range-thumb { width: 18px; height: 18px; border-radius: 50%;
          background: var(--indigo); border: 2px solid var(--porcelain-2); box-shadow: 0 0 8px var(--ind-40); }
        .persona-range:focus-visible { box-shadow: 0 0 0 3px var(--ind-10); }
      `}</style>

      <div className="space-y-16">
        <WhisperLine>她是谁，你又是谁——都在这页纸上慢慢显影</WhisperLine>

        {/* ── 助手人格 ─────────────────────────────────────────── */}
        <Reveal as="section" className="glass-card p-6" transition={cardTransition(0.1)}>
          <SectionHeader
            title="助手人格"
            subtitle="她如何说话、何时开口、说多少"
            right={
              personaReady && form ? (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-weak)" }}>
                  v{version}
                </span>
              ) : undefined
            }
          />

          {!personaReady ? (
            <LoadingDots label="正在翻开档案……" />
          ) : !form ? (
            <EmptyState message="人格档案暂时打不开——炉火熄了" />
          ) : (
            <div className="flex flex-col gap-8">
              {/* 预设 chips */}
              <div>
                <div className="text-xs mb-3" style={{ color: "var(--text-weak)" }}>预设</div>
                <div className="flex flex-wrap gap-2" role="tablist" aria-label="人格预设">
                  {Object.keys(PRESET_LABELS).map((id) => {
                    const active = form.preset_id === id;
                    return (
                      <button
                        key={id}
                        role="tab"
                        aria-selected={active}
                        onClick={() => choosePreset(id)}
                        className="px-4 py-2 rounded-full text-[13px] font-medium"
                        style={{
                          background: active ? "var(--ind-16)" : "transparent",
                          color: active ? "var(--indigo-deep)" : "var(--text-dim)",
                          border: `1px solid ${active ? "var(--edge-active)" : "var(--edge)"}`,
                          transition: "all 0.5s var(--ease-out)",
                        }}
                      >
                        {pick(PRESET_LABELS, id)}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 名字 / 称呼 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>名字</label>
                  <input
                    className="input-glow"
                    maxLength={20}
                    value={form.name}
                    onChange={(e) => patchForm({ name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>她如何称呼你</label>
                  <input
                    className="input-glow"
                    maxLength={20}
                    value={form.user_address}
                    onChange={(e) => patchForm({ user_address: e.target.value })}
                  />
                </div>
              </div>

              {/* 直接度 / 幽默度 滑杆 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                <RatingSlider
                  label="直接度"
                  low="委婉"
                  high="直接"
                  value={form.directness}
                  onChange={(v) => patchForm({ directness: v })}
                />
                <RatingSlider
                  label="幽默度"
                  low="严肃"
                  high="活泼"
                  value={form.humor}
                  onChange={(v) => patchForm({ humor: v })}
                />
              </div>

              {/* 主动性 / 回复长度 下拉 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>主动性</label>
                  <select
                    className="input-glow"
                    value={form.initiative}
                    onChange={(e) => patchForm({ initiative: e.target.value as PersonalityInitiative })}
                  >
                    {Object.keys(INITIATIVE_LABELS).map((k) => (
                      <option key={k} value={k}>
                        {pick(INITIATIVE_LABELS, k)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>回复长度</label>
                  <select
                    className="input-glow"
                    value={form.reply_length}
                    onChange={(e) => patchForm({ reply_length: e.target.value as PersonalityReplyLength })}
                  >
                    {Object.keys(REPLY_LENGTH_LABELS).map((k) => (
                      <option key={k} value={k}>
                        {pick(REPLY_LENGTH_LABELS, k)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 禁忌词 chips 输入 */}
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>
                  禁忌词（回车记下，点 × 删去）
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  {form.taboos.map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[12px]"
                      style={{ background: "var(--cin-10)", color: "var(--cinnabar-deep)" }}
                    >
                      {t}
                      <button
                        aria-label={`删去禁忌词 ${t}`}
                        onClick={() => patchForm({ taboos: form.taboos.filter((x) => x !== t) })}
                        style={{ color: "var(--cinnabar-deep)", opacity: 0.7 }}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    className="input-glow"
                    style={{ maxWidth: 220, padding: "6px 12px", fontSize: 13 }}
                    placeholder="不想听到的词……"
                    value={tabooInput}
                    onChange={(e) => setTabooInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addTaboo();
                      }
                    }}
                  />
                </div>
              </div>

              {/* 自定义指令 */}
              <div>
                <label className="block text-xs mb-2" style={{ color: "var(--text-weak)" }}>自定义指令</label>
                <textarea
                  className="input-glow"
                  rows={3}
                  maxLength={1000}
                  placeholder="还想叮嘱她什么……"
                  value={form.custom_instruction}
                  onChange={(e) => patchForm({ custom_instruction: e.target.value })}
                />
              </div>

              {/* 操作行 */}
              <div className="flex flex-wrap items-center gap-3">
                <button className="btn-ghost" onClick={handlePreview} disabled={!formValid || previewing}>
                  {previewing ? "试听中…" : "试听"}
                </button>
                <button className="btn-lumen" onClick={handleSave} disabled={!formValid || saving}>
                  {saving ? "保存中…" : "保存"}
                </button>
                {previewing && <LoadingDots label="她在试着开口……" />}
                {notice && (
                  <motion.span
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: EASE.out }}
                    className="text-[13px] px-3 py-1 rounded-full"
                    style={{ background: NOTICE_COLORS[notice.tone][0], color: NOTICE_COLORS[notice.tone][1] }}
                  >
                    {notice.text}
                  </motion.span>
                )}
              </div>

              {/* 试听三句：衬线低语卡 */}
              {preview && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(Object.keys(PREVIEW_LABELS) as (keyof PersonalityPreview)[]).map((k, i) => (
                    <motion.div
                      key={k}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.08, duration: 0.7, ease: EASE.out }}
                      className="rounded-2xl p-4"
                      style={{ background: "var(--ind-04)", border: "1px solid var(--edge)" }}
                    >
                      <Tag color="indigo">{PREVIEW_LABELS[k]}</Tag>
                      <p
                        className="serif mt-3"
                        style={{ fontSize: 14, lineHeight: 1.9, color: "var(--text-dim)" }}
                      >
                        {preview[k]}
                      </p>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Reveal>

        {/* ── 用户画像 ─────────────────────────────────────────── */}
        <Reveal as="section" className="glass-card p-6" transition={cardTransition(0.2)}>
          <SectionHeader
            title="用户画像"
            subtitle="九个维度：感知 → 当前；每一处都可以由你补充或修正"
            right={
              profile ? (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-weak)" }}>
                  v{profile.version}
                </span>
              ) : undefined
            }
          />

          {!profileReady ? (
            <LoadingDots label="画像正在显影……" />
          ) : !profile ? (
            <EmptyState message="画像暂时打不开——炉火熄了" />
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {DIMENSIONS.map((dim, i) => {
                  const inferredText = formatProfileValue(profile.inferred?.[dim]);
                  const effectiveText = formatProfileValue(profile.effective?.[dim]);
                  const differ = inferredText !== effectiveText && inferredText !== "——";
                  const drafting = draft?.dimension === dim;
                  return (
                    <motion.div
                      key={dim}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.04, duration: 0.7, ease: EASE.out }}
                      className="rounded-2xl p-4"
                      style={{
                        background: "var(--porcelain-2)",
                        border: `1px solid ${drafting ? "var(--edge-active)" : "var(--edge)"}`,
                        transition: "border-color 0.5s var(--ease-out)",
                      }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium" style={{ color: "var(--text-main)" }}>
                          {DIM_LABELS[dim]}
                        </span>
                        <div className="flex gap-1.5">
                          {(["add", "suppress"] as const).map((action) => (
                            <button
                              key={action}
                              onClick={() => (drafting && draft.action === action ? setDraft(null) : openDraft(dim, action))}
                              className="text-[12px] px-2.5 py-0.5 rounded-full"
                              style={{
                                background: action === "add" ? "var(--min-10)" : "var(--cin-10)",
                                color: action === "add" ? "var(--mineral-deep)" : "var(--cinnabar-deep)",
                                opacity: drafting && draft.action !== action ? 0.45 : 1,
                                transition: "all 0.5s var(--ease-out)",
                              }}
                            >
                              {ACTION_LABELS[action]}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="mt-3 space-y-1.5">
                        {differ && (
                          <div className="text-[12px]" style={{ color: "var(--text-weak)", lineHeight: 1.7 }}>
                            <span className="mr-2">感知</span>
                            {inferredText}
                          </div>
                        )}
                        <div className="text-sm" style={{ color: "var(--text-dim)", lineHeight: 1.8 }}>
                          {differ && (
                            <span className="text-[12px] mr-2" style={{ color: "var(--text-weak)" }}>
                              当前
                            </span>
                          )}
                          {effectiveText}
                        </div>
                      </div>

                      {drafting && (
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.5, ease: EASE.out }}
                          className="mt-4 space-y-2"
                        >
                          <input
                            className="input-glow"
                            style={{ padding: "8px 12px", fontSize: 13 }}
                            placeholder={draft.action === "add" ? "想补充什么……" : "希望修正为……"}
                            value={draftValue}
                            onChange={(e) => setDraftValue(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && submitFeedback()}
                          />
                          <input
                            className="input-glow"
                            style={{ padding: "8px 12px", fontSize: 13 }}
                            placeholder="依据或说明（可留空）"
                            value={draftEvidence}
                            onChange={(e) => setDraftEvidence(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && submitFeedback()}
                          />
                          <div className="flex gap-2">
                            <button
                              className="btn-lumen"
                              style={{ padding: "6px 16px", fontSize: 13 }}
                              onClick={submitFeedback}
                              disabled={draftBusy || !draftValue.trim()}
                            >
                              {draftBusy ? "记下中…" : "记下"}
                            </button>
                            <button
                              className="btn-ghost"
                              style={{ padding: "6px 16px", fontSize: 13 }}
                              onClick={() => setDraft(null)}
                            >
                              作罢
                            </button>
                          </div>
                        </motion.div>
                      )}
                    </motion.div>
                  );
                })}
              </div>

              {profile.change_summary && (
                <p className="serif mt-8" style={{ fontSize: 13, color: "var(--text-weak)", letterSpacing: "0.04em" }}>
                  {localizeDisplayText(profile.change_summary)}
                </p>
              )}

              {/* 已记下的反馈 */}
              {profile.feedback && profile.feedback.length > 0 && (
                <div className="mt-10 pt-6" style={{ borderTop: "1px solid var(--edge)" }}>
                  <div className="text-xs mb-4" style={{ color: "var(--text-weak)" }}>
                    已记下的反馈
                  </div>
                  <div className="space-y-3">
                    {profile.feedback.map((fb) => (
                      <div key={fb.id} className="flex flex-wrap items-center gap-2">
                        <Tag color="indigo">{DIM_LABELS[fb.dimension] || fb.dimension}</Tag>
                        <Tag color={fb.action === "add" ? "moss" : "bloom"}>
                          {ACTION_LABELS[fb.action] || fb.action}
                        </Tag>
                        <span className="text-sm flex-1" style={{ color: "var(--text-dim)", minWidth: 200 }}>
                          {localizeDisplayText(fb.value)}
                          {fb.evidence && (
                            <span className="text-[12px] ml-2" style={{ color: "var(--text-weak)" }}>
                              —— {localizeDisplayText(fb.evidence)}
                            </span>
                          )}
                        </span>
                        <span
                          style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-weak)" }}
                        >
                          {(fb.created_at || "").slice(0, 10)}
                        </span>
                        <button
                          className="text-[12px]"
                          style={{
                            color: deletingId === fb.id ? "var(--text-weak)" : "var(--cinnabar-deep)",
                            transition: "color 0.5s var(--ease-out)",
                          }}
                          disabled={deletingId === fb.id}
                          onClick={() => removeFeedback(fb.id)}
                        >
                          {deletingId === fb.id ? "删去中…" : "删去"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </Reveal>
      </div>
    </>
  );
}

/** 暖金滑杆：1~5 档，带端点语义 */
function RatingSlider({
  label,
  low,
  high,
  value,
  onChange,
}: {
  label: string;
  low: string;
  high: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-xs" style={{ color: "var(--text-weak)" }}>
          {label}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--indigo)" }}>
          {value} / 5
        </span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        step={1}
        value={value}
        aria-label={label}
        className="persona-range w-full"
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <div className="flex justify-between mt-1.5 text-[11px]" style={{ color: "var(--text-weak)" }}>
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  );
}
