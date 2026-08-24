"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Ban, Plus, RefreshCw, Trash2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { ProfileDimension, ProfileFeedbackInput, ProfileResponse, ProfileValue } from "@/lib/types";

const dimensions: Array<[ProfileDimension, string]> = [
  ["personality", "性格特征"], ["values", "价值观"], ["goals", "目标"], ["habits", "习惯"], ["skills", "技能"], ["knowledge", "知识"], ["thinking_patterns", "思考方式"], ["preferences", "偏好"], ["affective_baseline", "情绪基线"],
];
const labels: Record<ProfileDimension, string> = {
  personality: "性格特征",
  values: "价值观",
  goals: "目标",
  habits: "习惯",
  skills: "技能",
  knowledge: "知识",
  thinking_patterns: "思考方式",
  preferences: "偏好",
  affective_baseline: "情绪基线",
};

function valuesOf(value: ProfileValue | undefined): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (value === null || value === undefined || value === "") return [];
  return [String(value)];
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [dimension, setDimension] = useState<ProfileDimension>("preferences");
  const [value, setValue] = useState("");
  const [evidence, setEvidence] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try { setProfile(await api.profile()); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "画像读取失败，请稍后重试。"); }
  };
  useEffect(() => { void load(); }, []);

  const submit = async (action: ProfileFeedbackInput["action"]) => {
    if (!value.trim() || !evidence.trim()) return;
    setPending(true);
    setError("");
    try {
      await api.addProfileFeedback({ dimension, value: value.trim(), action, evidence_kind: "user_statement", evidence: evidence.trim() });
      setValue(""); setEvidence("");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "反馈提交失败，请稍后重试。");
    } finally { setPending(false); }
  };

  const deactivate = async (id: string) => {
    setPending(true); setError("");
    try { await api.deleteProfileFeedback(id); await load(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "反馈停用失败，请稍后重试。"); }
    finally { setPending(false); }
  };

  return (
    <div className="settings-page">
      <header className="settings-header">
        <div><p>ASSISTANT / PROFILE</p><h1>我的画像</h1><span>蒸馏推断、实际生效内容与用户反馈分开呈现。</span></div>
        <button className="control-button" onClick={() => void load()} disabled={pending}><RefreshCw size={15} />重新加载</button>
      </header>
      {error && <div role="alert" className="settings-alert is-error"><AlertTriangle size={16} />{error}</div>}
      {profile ? (
        <>
          <section className="profile-meta">
            <div><span>画像版本</span><strong>v{profile.version}</strong></div>
            <div><span>本次变化摘要</span><p>{profile.change_summary || "当前版本没有变化摘要。"}</p></div>
          </section>
          <div className="profile-compare">
            <ProfileColumn testId="profile-inferred" title="系统推断" note="由记忆与蒸馏流程生成，尚未叠加你的反馈。" data={profile.inferred} />
            <ProfileColumn testId="profile-effective" title="当前生效画像" note="系统推断叠加有效的添加与抑制反馈。" data={profile.effective} />
          </div>

          <section className="settings-section feedback-composer">
            <div className="section-title"><div><h2>校正画像</h2><p>只能修正已知画像维度；依据必须是你的明确陈述。</p></div></div>
            <div className="field-grid three">
              <label className="control-field"><span>画像维度</span><select value={dimension} onChange={(event) => setDimension(event.target.value as ProfileDimension)}>{dimensions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
              <label className="control-field"><span>反馈内容</span><input value={value} onChange={(event) => setValue(event.target.value)} placeholder="例如：更喜欢茶" /></label>
              <label className="control-field"><span>反馈依据</span><input value={evidence} onChange={(event) => setEvidence(event.target.value)} placeholder="例如：我明确说明更喜欢茶" /></label>
            </div>
            <div className="settings-actions align-left">
              <button className="control-button is-primary" disabled={pending || !value.trim() || !evidence.trim()} onClick={() => void submit("add")}><Plus size={15} />添加或纠正</button>
              <button className="control-button" disabled={pending || !value.trim() || !evidence.trim()} onClick={() => void submit("suppress")}><Ban size={15} />抑制此项</button>
            </div>
          </section>

          <section className="settings-section" data-testid="profile-evidence">
            <div className="section-title"><div><h2>反馈与证据</h2><p>停用会撤销这条反馈对生效画像的影响，不删除推断来源。</p></div><span>{profile.feedback.length} 条</span></div>
            <div className="feedback-list">
              {profile.feedback.length === 0 ? <p className="settings-empty">还没有有效的用户反馈。</p> : profile.feedback.map((item) => (
                <article key={item.id}>
                  <div><span>{labels[item.dimension]}</span><strong>{item.action === "add" ? "添加 / 纠正" : "抑制"}</strong></div>
                  <p>{item.value}</p><small>明确依据：{item.evidence}</small>
                  <button type="button" aria-label={`停用反馈：${item.value}`} disabled={pending} onClick={() => void deactivate(item.id)}><Trash2 size={14} />停用</button>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : <p className="settings-loading">正在读取画像…</p>}
    </div>
  );
}

function ProfileColumn({ testId, title, note, data }: { testId: string; title: string; note: string; data: ProfileResponse["inferred"] }) {
  return <section className="settings-section profile-column" data-testid={testId}><div className="section-title"><div><h2>{title}</h2><p>{note}</p></div></div><div className="dimension-list">{dimensions.map(([key, label]) => { const values = valuesOf(data[key]); return <article key={key}><span>{label}</span><div>{values.length ? values.map((item) => <p key={item}>{item}</p>) : <p className="is-empty">暂无内容</p>}</div></article>; })}</div></section>;
}
