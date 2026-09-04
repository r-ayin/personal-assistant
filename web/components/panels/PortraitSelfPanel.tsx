"use client";

import { api } from "@/lib/api";
import { HonestEmpty, TraitBar, parseJson, useAsync } from "@/components/portrait-bits";
import { SectionHeader } from "@/components/ui";
import {
  GROWTH_ZH, LEVEL_ZH, SCHWARTZ_ZH, STALE_GOAL_DAYS, STALE_TASK_DAYS, TASK_TYPE_ZH,
} from "@/lib/labels-zh";
import type { PortraitGrowth } from "@/lib/types";

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

      {!!goals.length && (() => {
        const active = goals.filter((g) => (g.stale_days ?? 0) <= STALE_GOAL_DAYS);
        const stale = goals.filter((g) => (g.stale_days ?? 0) > STALE_GOAL_DAYS);
        return (
          <>
            {!!active.length && (
              <section>
                <SectionHeader title="目标" subtitle={`近 ${STALE_GOAL_DAYS} 天内仍活跃 · 中文层级标签`} />
                <div className="glass-card p-6 space-y-3 cv-auto">
                  {active.map((g) => (
                    <div key={g.id} className="flex items-baseline justify-between gap-4 border-b border-[var(--hairline)] pb-2">
                      <span className="text-[13.5px] text-[var(--ink-900)]">{g.text_gist}</span>
                      <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                        {LEVEL_ZH[g.level] ?? g.level}
                        {g.possible_self_type ? ` · ${g.possible_self_type}` : ""}
                        {g.commitment_evidence_count ? ` · 证据${g.commitment_evidence_count}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {!!stale.length && (
              <section className="opacity-55">
                <SectionHeader
                  title={`过时目标（${stale.length}）`}
                  subtitle={`最后活跃超过 ${STALE_GOAL_DAYS} 天，不再当作现状复述`}
                />
                <div className="glass-card p-6 space-y-2 cv-auto">
                  {stale.map((g) => (
                    <div key={g.id} className="flex items-baseline justify-between gap-4">
                      <span className="text-[12.5px] text-[var(--text-dim)] line-through decoration-[var(--ink-18)]">
                        {g.text_gist}
                      </span>
                      <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                        过时 {g.stale_days} 天 · {LEVEL_ZH[g.level] ?? g.level}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        );
      })()}

      {!!tasks.length && (() => {
        const active = tasks.filter((t) => (t.stale_days ?? 0) <= STALE_TASK_DAYS);
        const stale = tasks.filter((t) => (t.stale_days ?? 0) > STALE_TASK_DAYS);
        const row = (t: (typeof tasks)[number], dim: boolean) => (
          <div key={t.id} className="flex items-baseline justify-between gap-4">
            <span className={`text-[13px] ${dim ? "text-[var(--text-dim)] line-through decoration-[var(--ink-18)]" : "text-[var(--ink-700)]"}`}>
              {t.zeigarnik_flag === 1 && !dim && <span className="mr-1 text-[var(--cinnabar)]">◦</span>}
              {t.raw_text}
            </span>
            <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
              {TASK_TYPE_ZH[t.type] ?? t.type}
              {t.committed_to_whom ? ` · 对 ${t.committed_to_whom}` : ""}
              {t.source_ts ? ` · ${(t.source_ts || "").slice(5, 10)}` : ""}
              {dim ? ` · 过时 ${t.stale_days} 天` : ""}
            </span>
          </div>
        );
        return (
          <>
            {!!active.length && (
              <section>
                <SectionHeader
                  title="未闭环待办"
                  subtitle={`原话在 ${STALE_TASK_DAYS} 天内 · ◦ = 悬而未决（Zeigarnik）`}
                />
                <div className="glass-card p-6 space-y-2 cv-auto">{active.map((t) => row(t, false))}</div>
              </section>
            )}
            {!!stale.length && (
              <section className="opacity-55">
                <SectionHeader
                  title={`过时待办（${stale.length}）`}
                  subtitle={`原话超过 ${STALE_TASK_DAYS} 天，不再当作当前待办`}
                />
                <div className="glass-card p-6 space-y-2 cv-auto">{stale.map((t) => row(t, true))}</div>
              </section>
            )}
          </>
        );
      })()}

      {!!values.length && (
        <section>
          <SectionHeader title="价值观 / 理想" subtitle="Schwartz 价值域（中文）；跨会话复现才计入" />
          <div className="glass-card p-6 space-y-2 cv-auto">
            {values.map((v) => (
              <div key={v.id} className="flex items-baseline justify-between gap-4">
                <span className="text-[13px] text-[var(--ink-700)]">{v.statement}</span>
                <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                  {SCHWARTZ_ZH[v.schwartz_domain] ?? v.schwartz_domain ?? "—"} · 跨会话复现 {v.recurrence_count} 次
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
                  <span className="text-[13px] text-[var(--ink-700)]">
                    {GROWTH_ZH[g.dimension] ?? g.dimension}
                  </span>
                  <span className="font-mono text-[12px] text-[var(--text-weak)]">
                    {score == null ? "无数据" : `${score.toFixed(2)} · 行为代理`}
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
