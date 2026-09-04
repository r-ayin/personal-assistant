"use client";

import { api } from "@/lib/api";
import { HonestEmpty, TraitBar, parseJson, useAsync } from "@/components/portrait-bits";
import { SectionHeader } from "@/components/ui";
import type { PortraitGrowth } from "@/lib/types";

const LEVEL_LABEL: Record<string, string> = {
  runway: "下一步", project: "项目", area: "责任领域",
  goal_1_2y: "1–2 年目标", vision_3_5y: "3–5 年愿景", purpose: "目的",
};

/** 「我」tab：七维自我画像。全部来自 /portrait/self，空则诚实空态。 */
export default function PortraitSelfPanel() {
  const { loading, error, data } = useAsync(() => api.portraitSelf(), []);

  if (loading) return <HonestEmpty title="正在从消息里读取你的画像…" />;
  if (error) return <HonestEmpty title="连不上后端" hint={error} />;
  if (!data?.available) return <HonestEmpty title="画像库尚未建立" hint="跑一轮 memcore 抽取后这里会长出内容" />;

  const traits = (data.traits ?? []).filter((t) => t.promoted === 1);
  const unpromoted = (data.traits ?? []).filter((t) => t.promoted !== 1);
  const goals = data.goals ?? [];
  const tasks = data.tasks ?? [];
  const values = data.values ?? [];
  const affect = (data.affect ?? [])[0];
  const growth = data.growth ?? [];
  const empty = !traits.length && !goals.length && !tasks.length && !values.length;

  return (
    <div className="space-y-10">
      {data.person?.profile_card && (
        <section>
          <SectionHeader title="档案卡" subtitle="Letta 式 memory block，可直接进 system prompt" />
          <pre className="glass-card p-6 whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed text-[var(--ink-700)]">
            {data.person.profile_card}
          </pre>
        </section>
      )}

      {empty && (
        <HonestEmpty
          title="画像正在从你的消息里长出来"
          hint="目前还没有足够证据升格出任何稳定维度——这不是空白错误，是诚实"
        />
      )}

      {!!traits.length && (
        <section>
          <SectionHeader title="特质（密度分布）" subtitle="mean±sd，非标签；代理推断，非量表实测" />
          <div className="glass-card p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {traits.map((t) => <TraitBar key={t.dimension} t={t} />)}
          </div>
          {!!unpromoted.length && (
            <p className="mt-2 text-[12px] text-[var(--text-weak)]">
              另有 {unpromoted.length} 个维度独立会话不足 3，未升格，下面弱化展示。
            </p>
          )}
        </section>
      )}
      {!traits.length && !!unpromoted.length && (
        <section>
          <SectionHeader title="特质（未升格）" subtitle="独立会话 <3，暂不作为稳定特质" />
          <div className="glass-card p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {unpromoted.map((t) => <TraitBar key={t.dimension} t={t} />)}
          </div>
        </section>
      )}

      {!!goals.length && (
        <section>
          <SectionHeader title="目标" subtitle="GTD Horizons + possible selves" />
          <div className="glass-card p-6 space-y-3 cv-auto">
            {goals.map((g) => (
              <div key={g.id} className="flex items-baseline justify-between gap-4 border-b border-[var(--hairline)] pb-2">
                <span className="text-[13.5px] text-[var(--ink-900)]">{g.text_gist}</span>
                <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                  {LEVEL_LABEL[g.level] ?? g.level}
                  {g.possible_self_type ? ` · ${g.possible_self_type}` : ""}
                  {g.commitment_evidence_count ? ` · 证据${g.commitment_evidence_count}` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!!tasks.length && (
        <section>
          <SectionHeader title="未闭环任务" subtitle="GTD 类型； Zeigarnik 标记 = 悬而未决" />
          <div className="glass-card p-6 space-y-2 cv-auto">
            {tasks.map((t) => (
              <div key={t.id} className="flex items-baseline justify-between gap-4">
                <span className="text-[13px] text-[var(--ink-700)]">
                  {t.zeigarnik_flag === 1 && <span className="mr-1 text-[var(--cinnabar)]">◦</span>}
                  {t.raw_text}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                  {t.type}{t.committed_to_whom ? ` · 对 ${t.committed_to_whom}` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!!values.length && (
        <section>
          <SectionHeader title="价值观 / 理想" subtitle="Schwartz 域；跨会话复现才计入" />
          <div className="glass-card p-6 space-y-2 cv-auto">
            {values.map((v) => (
              <div key={v.id} className="flex items-baseline justify-between gap-4">
                <span className="text-[13px] text-[var(--ink-700)]">{v.statement}</span>
                <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                  {v.schwartz_domain || "—"} · 复现{v.recurrence_count}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {affect && affect.eligible === 1 && (
        <section>
          <SectionHeader title="情感剖面" subtitle={`n=${affect.n}；惯性=lag-1 自相关；粒度=标签熵`} />
          <div className="glass-card p-6">
            {([
              ["正向均值", affect.pa_mean],
              ["负向均值", affect.na_mean],
              ["波动 MSSD", affect.variability_mssd],
              ["惯性", affect.inertia],
              ["粒度", affect.granularity],
            ] as [string, number | null][]).map(([label, v]) => (
              <div key={label} className="flex items-baseline justify-between gap-4 py-2 border-b border-[var(--hairline)]">
                <span className="text-[13px] text-[var(--ink-700)]">{label}</span>
                <span className="font-mono text-[12px] text-[var(--ink-900)]">
                  {v == null ? "—" : v.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      {affect && affect.eligible !== 1 && (
        <HonestEmpty title="情感剖面样本不足" hint={affect.ineligible_reason} />
      )}

      {!!growth.length && (
        <section>
          <SectionHeader title="成长（Ryff 六维代理）" subtitle="行为代理推断，非量表实测" />
          <div className="glass-card p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {growth.map((g: PortraitGrowth) => {
              const hist = parseJson<{ proxy_score?: number }[]>(g.score_history, []);
              const score = hist[0]?.proxy_score;
              return (
                <div key={g.id} className="flex items-baseline justify-between gap-3">
                  <span className="text-[13px] text-[var(--ink-700)]">{g.dimension}</span>
                  <span className="font-mono text-[12px] text-[var(--text-weak)]">
                    {score == null ? "无数据" : score.toFixed(2)} · 代理
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
