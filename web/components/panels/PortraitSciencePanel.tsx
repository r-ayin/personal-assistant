"use client";

import { useReducedMotion } from "framer-motion";
import Reveal from "@/components/Reveal";
import { Rich, SectionHeader } from "@/components/ui";
import {
  HONESTY_RULES, LAYER_SCIENCE, METRICS_SCIENCE, SCIENCE_GROUPS,
} from "@/lib/metrics-science";
import type { MetricScience } from "@/lib/metrics-science";
import { METRIC_ZH } from "@/lib/labels-zh";

/** 单张指标卡：出处 / 直觉 / 公式 / 怎么读 / 效度四件 / 局限 */
function ScienceCard({ id, s, onGoMetrics }: {
  id: string;
  s: MetricScience;
  onGoMetrics: () => void;
}) {
  return (
    <article id={id} className="glass-card cv-auto p-6">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="serif text-[17px] font-semibold text-[var(--ink-900)]">{s.zh}</h3>
        <span className="shrink-0 font-mono text-[10.5px] text-[var(--text-weak)]">{id.replace("sci-", "")}</span>
      </div>
      <p className="mt-1 text-[11.5px] text-[var(--text-dim)]">出处：<Rich text={s.origin} /></p>

      <p className="mt-3 text-[13px] leading-relaxed text-[var(--ink-700)]"><Rich text={s.intuition} /></p>
      {s.formula && (
        <pre className="mt-2 overflow-x-auto rounded-md bg-[var(--ink-02)] px-3 py-2 font-mono text-[11.5px] leading-relaxed text-[var(--ink-700)]">
          {s.formula}
        </pre>
      )}

      <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--text-dim)]">
        <span className="font-medium text-[var(--ink-700)]">怎么读：</span><Rich text={s.read} />
      </p>
      {METRIC_ZH[id.replace("sci-", "")] && (
        <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-weak)]">
          高=<Rich text={METRIC_ZH[id.replace("sci-", "")].high} />　低=<Rich text={METRIC_ZH[id.replace("sci-", "")].low} />
        </p>
      )}

      <dl className="mt-3 space-y-1.5 border-t border-[var(--hairline)] pt-3 text-[11.5px] leading-relaxed">
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-[var(--indigo)]">零假设基线</dt>
          <dd className="text-[var(--text-dim)]"><Rich text={s.validity.null_kind} /></dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-[var(--indigo)]">置信区间</dt>
          <dd className="text-[var(--text-dim)]"><Rich text={s.validity.ci_method} /></dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-[var(--indigo)]">出数门槛</dt>
          <dd className="text-[var(--text-dim)]"><Rich text={s.validity.gate} /></dd>
        </div>
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium text-[var(--ochre)]">已知局限</dt>
          <dd className="text-[var(--text-dim)]"><Rich text={s.validity.limits} /></dd>
        </div>
      </dl>
      {s.caveats && (
        <p className="mt-2 rounded-md bg-[var(--cin-04)] px-3 py-2 text-[11.5px] leading-relaxed text-[var(--cinnabar-deep)]">
          <Rich text={s.caveats} />
        </p>
      )}
      <button
        type="button"
        onClick={onGoMetrics}
        className="btn-ghost mt-4 px-3 py-1 text-[11.5px]"
      >
        在「复杂度指标」查看你的数值 →
      </button>
    </article>
  );
}

/**
 * 「指标科普」整版 tab：只讲方法，不放你的任何数字。
 * 长页性能：卡片走 .cv-auto（content-visibility），入场只给组标题 Reveal，
 * 25 张卡不各自挂停摆守卫定时器。
 */
export default function PortraitSciencePanel({ onGoMetrics }: { onGoMetrics: () => void }) {
  const reduced = useReducedMotion();
  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: reduced ? "auto" : "smooth",
      block: "start",
    });
  };
  const byGroup = (gid: string) =>
    Object.entries(METRICS_SCIENCE).filter(([, s]) => s.group === gid);

  return (
    <div className="lg:grid lg:grid-cols-[168px_minmax(0,1fr)] lg:gap-8">
      {/* 诚实规则 */}
      <div className="lg:col-start-2">
        <SectionHeader
          title="先讲五条规矩"
          subtitle="这一页只解释方法，不放你的任何数字；你的数值在「复杂度指标」tab"
        />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {HONESTY_RULES.map((r, i) => (
            <Reveal key={r.title} as="section" className="glass-card p-5" delay={i * 0.06}>
              <h3 className="serif text-[15px] font-semibold text-[var(--ink-900)]">{r.title}</h3>
              <p className="mt-2 text-[12.5px] leading-relaxed text-[var(--text-dim)]"><Rich text={r.body} /></p>
            </Reveal>
          ))}
        </div>
      </div>

      {/* 锚点轨 */}
      <nav className="hidden lg:block sticky top-24 self-start mt-10 space-y-1" aria-label="指标分组">
        {SCIENCE_GROUPS.map((g) => (
          <button
            key={g.id} type="button" onClick={() => jump(`grp-${g.id}`)}
            className="block w-full rounded-md px-3 py-1.5 text-left text-[12px] text-[var(--text-dim)] hover:bg-[var(--ink-04)] hover:text-[var(--ink-900)]"
          >
            {g.zh}
          </button>
        ))}
        <button
          type="button" onClick={() => jump("grp-layers")}
          className="block w-full rounded-md px-3 py-1.5 text-left text-[12px] text-[var(--text-dim)] hover:bg-[var(--ink-04)] hover:text-[var(--ink-900)]"
        >
          画像三层
        </button>
      </nav>

      <div className="lg:col-start-2 mt-12 space-y-14">
        {SCIENCE_GROUPS.map((g) => (
          <section key={g.id} id={`grp-${g.id}`} className="scroll-mt-24">
            <Reveal as="div">
              <SectionHeader title={g.zh} subtitle={g.blurb} />
            </Reveal>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              {byGroup(g.id).map(([name, s]) => (
                <ScienceCard key={name} id={`sci-${name}`} s={s} onGoMetrics={onGoMetrics} />
              ))}
            </div>
          </section>
        ))}

        <section id="grp-layers" className="scroll-mt-24">
          <Reveal as="div">
            <SectionHeader
              title="画像三层：特质 / 情感 / 成长"
              subtitle="这三层不是复杂科学指标，是心理学构念的行为代理；方法学与局限单独讲"
            />
          </Reveal>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {(Object.entries(LAYER_SCIENCE) as [string, MetricScience][]).map(([k, s]) => (
              <ScienceCard key={k} id={`sci-${k}`} s={s} onGoMetrics={onGoMetrics} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
