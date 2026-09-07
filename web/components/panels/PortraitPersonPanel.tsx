"use client";

import { api } from "@/lib/api";
import { HonestEmpty, MetricRow, TraitBar, parseJson, useAsync } from "@/components/portrait-bits";
import { TraitDensityChart } from "@/components/charts";
import { SectionHeader, Tag } from "@/components/ui";
import { ALIAS_SPACE_ZH, SCHWARTZ_ZH } from "@/lib/labels-zh";
import type { PersonMoment, PortraitTrait, TraitDist } from "@/lib/types";

function MomentCard({ m }: { m: PersonMoment }) {
  const tags = parseJson<string[]>(m.tags, []);
  return (
    <article className={`glass-card p-5 ${m.recalled === 0 ? "border-l-[3px] border-l-[var(--cinnabar)]" : ""}`}>
      <p className="serif text-[14px] leading-relaxed text-[var(--ink-900)]">“{m.verbatim_quote}”</p>
      {m.narrative && (
        <p className="mt-2 text-[12.5px] leading-relaxed text-[var(--text-dim)]">{m.narrative}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {tags.map((t) => <Tag key={t}>{t}</Tag>)}
        <span className="ml-auto font-mono text-[11px] text-[var(--text-weak)]">
          {m.ts.slice(0, 16)}{m.recalled === 0 ? " · 未归还" : ""}
        </span>
      </div>
    </article>
  );
}

/** 单人档案 tab：别名四空间 / 特质 / 价值观 / 时刻 / 指标 */
export default function PortraitPersonPanel({ personId }: { personId: string | null }) {
  const { loading, error, data } = useAsync(
    () => (personId ? api.portraitPerson(personId) : Promise.resolve(null)),
    [personId],
  );

  if (!personId) {
    return <HonestEmpty title="从「关系圈」点一个人进来" hint="或带 ?person=<id> 直接打开" />;
  }
  if (loading) return <HonestEmpty title="正在读取这个人的档案…" />;
  if (error) return <HonestEmpty title="连不上后端" hint={error} />;
  if (!data?.available || !data.person) {
    return <HonestEmpty title="没有这个人的档案" hint={personId} />;
  }

  const p = data.person;
  const aliases = data.aliases ?? [];
  const traits = data.traits ?? [];
  const values = data.values ?? [];
  const moments = data.moments ?? [];
  const metrics = data.metrics ?? [];
  const unrecalled = moments.filter((m) => m.recalled === 0);

  return (
    <div className="space-y-10">
      <section>
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="serif text-[22px] font-semibold text-[var(--ink-900)]">
            {p.display_name || p.person_id}
          </h2>
          {p.role && <span className="rounded-full bg-[var(--cin-08)] px-3 py-1 text-[12px] text-[var(--cinnabar)]">{p.role}</span>}
        </div>
        {p.profile_card && (
          <pre className="glass-card mt-4 p-5 whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-[var(--ink-700)]">
            {p.profile_card}
          </pre>
        )}
        {!!aliases.length && (
          <div className="mt-3 flex flex-wrap gap-2">
            {aliases.map((a, i) => (
              <span key={`${a.alias_space}-${a.label}-${i}`} className="rounded-full bg-[var(--ink-06)] px-2.5 py-[3px] font-mono text-[11px] text-[var(--text-dim)]">
                {a.label}<span className="ml-1 text-[var(--text-weak)]">({ALIAS_SPACE_ZH[a.alias_space] ?? a.alias_space}·{a.evidence_count} 条)</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {!!traits.length && (
        <section>
          <SectionHeader title="特质（密度分布）" subtitle="代理推断；未升格的弱化展示" />
          <div className="glass-card p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {traits.map((t: PortraitTrait) => (
              <div key={t.dimension}>
                <TraitBar t={t} />
                <TraitDensityChart
                  dist={parseJson<TraitDist | null>(t.dist, null)}
                  promoted={t.promoted === 1}
                  isProxy={t.is_proxy === 1}
                  nConv={t.n_independent_conv}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {!!values.length && (
        <section>
          <SectionHeader title="价值观" subtitle="Schwartz 域；跨会话复现计数" />
          <div className="glass-card p-6 space-y-2 cv-auto">
            {values.map((v) => (
              <div key={v.id} className="flex items-baseline justify-between gap-4">
                <span className="text-[13px] text-[var(--ink-700)]">{v.statement}</span>
                <span className="shrink-0 font-mono text-[11px] text-[var(--text-weak)]">
                  {SCHWARTZ_ZH[v.schwartz_domain] ?? v.schwartz_domain ?? "—"} · 复现{v.recurrence_count}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!!unrecalled.length && (
        <section>
          <SectionHeader title="未归还的时刻" subtitle="归还时机由你决定，系统不主动推" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 cv-auto">
            {unrecalled.map((m) => <MomentCard key={m.id} m={m} />)}
          </div>
        </section>
      )}
      {!!moments.length && unrecalled.length !== moments.length && (
        <section>
          <SectionHeader title="已归还的时刻" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 cv-auto opacity-70">
            {moments.filter((m) => m.recalled === 1).map((m) => <MomentCard key={m.id} m={m} />)}
          </div>
        </section>
      )}

      {!!metrics.length && (
        <section>
          <SectionHeader title="复杂度指标" subtitle="eligible=0 灰显并给理由" />
          <div className="glass-card p-6 cv-auto">
            {metrics.map((m, i) => (
              <MetricRow key={`${m.name}-${i}`} m={{ ...m, subject_id: p.person_id, subject_kind: "person" }} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
