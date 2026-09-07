"use client";

import { useEffect, useState } from "react";
import { DIM_EXPLAIN, METRIC_SUBS, METRIC_ZH, PERSON_KIND_ZH } from "@/lib/labels-zh";
import { interpretMetric, interpretTrait } from "@/lib/metrics-read";
import { MetricDetailChart, NullBandChart } from "@/components/charts";
import type { PortraitMetricRow, PortraitTrait, TraitDist } from "@/lib/types";

/** JSON 列解析：失败回退 null，绝不编造数值 */
export function parseJson<T>(s: string | null | undefined, fallback: T): T {
  if (!s) return fallback;
  try {
    return JSON.parse(s) as T;
  } catch {
    return fallback;
  }
}

/** 诚实空态：说明在等什么，不放任何示例数字 */
export function HonestEmpty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="glass-card p-8 text-center">
      <p className="serif text-[15px] text-[var(--ink-700)]">{title}</p>
      {hint && <p className="mt-2 text-[13px] text-[var(--text-weak)]">{hint}</p>}
    </div>
  );
}

const DIM_LABEL: Record<string, string> = {
  ipc_agency: "支配–顺从",
  ipc_communion: "温暖–冷漠",
  attach_anxiety: "依恋焦虑",
  attach_avoidance: "依恋回避",
  big5_N: "神经质",
  big5_E: "外向",
  big5_O: "开放",
  big5_A: "宜人",
  big5_C: "尽责",
};

/** 特质分布条：mean±sd，标观测数与是否升格；未升格视觉弱化 */
export function TraitBar({ t }: { t: PortraitTrait }) {
  const d = parseJson<TraitDist | null>(t.dist, null);
  const promoted = t.promoted === 1;
  const mean = d?.mean;
  const sd = d?.sd;
  // mean ∈ [-1,1] → 位置 0..100%
  const pos = mean == null ? 50 : Math.max(0, Math.min(100, ((mean + 1) / 2) * 100));
  const width = sd == null ? 0 : Math.max(2, Math.min(100, sd * 100));
  return (
    <div className={promoted ? "" : "opacity-45"}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] font-medium text-[var(--ink-700)]">
          {DIM_LABEL[t.dimension] ?? t.dimension}
        </span>
        <span className="font-mono text-[11px] text-[var(--text-weak)]">
          {mean == null
            ? "不可解析"
            : `${mean >= 0 ? "+" : ""}${mean.toFixed(2)} ± ${(sd ?? 0).toFixed(2)} · 观测 ${d?.n_observations ?? 0} · 独立会话 ${t.n_independent_conv}`}
        </span>
      </div>
      <div className="relative mt-1 h-[6px] rounded-full bg-[var(--ink-06)]">
        <div className="absolute top-0 h-full rounded-full bg-[var(--ink-18)]"
          style={{ left: `${Math.max(0, pos - width / 2)}%`, width: `${width}%` }} />
        <div className="absolute top-[-2px] h-[10px] w-[2px] bg-[var(--cinnabar)]"
          style={{ left: `${pos}%` }} />
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-weak)]">
        {DIM_EXPLAIN[t.dimension] ?? ""}
        {" "}
        {promoted
          ? t.is_proxy === 1 ? "· 代理推断，非量表实测" : ""
          : `· 独立会话 ${t.n_independent_conv}/3，未升格为稳定特质`}
      </p>
      {(() => {
        const rd = interpretTrait(mean ?? null, sd ?? null, d?.n_observations ?? 0, promoted);
        if (!rd) return null;
        return (
          <p className="mt-1 rounded-md bg-[var(--ind-06)] px-2.5 py-1.5 text-[11.5px] leading-relaxed text-[var(--ink-700)]">
            <span className="font-medium text-[var(--indigo-deep)]">你的数怎么读：</span>{rd}
          </p>
        );
      })()}
    </div>
  );
}

/** 指标行：中文名 + 用途 + 数值/CI/样本 + 对比随机基线的结论 + 高/低含义。
 *  rqa 额外展开 RR/DET/ENTR/Lmax 四子量（原本就是四个量，不能压成一个数）。
 *  eligible=0 灰显并给理由，不编数字。 */
export function MetricRow({ m }: { m: PortraitMetricRow }) {
  const ok = m.eligible === 1;
  const zh = METRIC_ZH[m.name];
  const nb = parseJson<Record<string, any> | null>(m.null_baseline, null);
  const p = nb?.p_value;
  const nullMean = nb?.null_mean;
  const above = p != null && p < 0.05;
  const detail = nb?.detail as Record<string, any> | undefined;
  const ciBy = (detail?.ci_by_measure ?? {}) as Record<string, [number, number]>;
  const pBy = (detail?.p_value_by_measure ?? {}) as Record<string, number>;
  const nullBy = (detail?.null_mean_by_measure ?? {}) as Record<string, number>;

  return (
    <div className={`py-3 border-b border-[var(--hairline)] ${ok ? "" : "opacity-45"}`}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-[13px] font-medium text-[var(--ink-700)]">
          {zh?.zh ?? m.name}
          <span className="ml-2 font-mono text-[11px] font-normal text-[var(--text-weak)]">
            {PERSON_KIND_ZH[m.subject_kind] ?? m.subject_kind}·{m.subject_id.slice(0, 12)}
          </span>
        </span>
        <span className="shrink-0 text-right font-mono text-[12px]">
          {ok ? (
            <span className="text-[var(--ink-900)]">
              {m.value == null ? "—" : m.value.toFixed(3)}
              <span className="text-[var(--text-weak)]">
                {" "}CI [{m.ci_low?.toFixed(2) ?? "—"}, {m.ci_high?.toFixed(2) ?? "—"}] 样本 {m.n ?? 0}
              </span>
            </span>
          ) : (
            <span className="text-[var(--text-weak)]">{m.ineligible_reason || "样本不足"}</span>
          )}
        </span>
      </div>

      {zh && <p className="mt-1 text-[11.5px] leading-relaxed text-[var(--text-dim)]">{zh.purpose}</p>}

      {ok && p != null && (
        <p className="mt-1 text-[11px] text-[var(--text-weak)]">
          对比你自己的随机打乱基线{nullMean != null ? `（${Number(nullMean).toFixed(3)}）` : ""}：
          p={Number(p).toFixed(3)} → {above ? "高于随机，结构真实存在" : "与随机无异，别当结论"}
        </p>
      )}
      {ok && (
        <NullBandChart
          observed={m.value} ciLow={m.ci_low} ciHigh={m.ci_high}
          nullMean={nullMean} q025={nb?.null_q025} q975={nb?.null_q975}
        />
      )}
      {ok && detail && <MetricDetailChart name={m.name} detail={detail} />}
      {ok && (() => {
        const rd = interpretMetric(m.name, m.value, nb, detail ?? null);
        if (!rd) return null;
        return (
          <p className="mt-1.5 rounded-md bg-[var(--ind-06)] px-2.5 py-1.5 text-[12px] leading-relaxed text-[var(--ink-700)]">
            <span className="font-medium text-[var(--indigo-deep)]">你的数怎么读：</span>{rd}
          </p>
        );
      })()}
      {zh && ok && (
        <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-weak)]">
          高={zh.high}　低={zh.low}
        </p>
      )}

      {ok && m.ci_low != null && m.ci_high != null && Math.abs(m.ci_high - m.ci_low) < 1e-9 && (
        <p className="mt-1 text-[11px] text-[var(--text-weak)]">
          CI 不可用：留一块刀切不改变这个统计量，区间退化为零宽，别当成"完全确定"。
        </p>
      )}

      {ok && detail && (METRIC_SUBS[m.name] ?? []).length > 0 && (
        <div className="mt-2 space-y-1 rounded-md bg-[var(--ink-02)] p-2">
          {(METRIC_SUBS[m.name] ?? []).map(({ key, zh: subZh }) => {
            const ci = ciBy[key];
            const pv = pBy[key];
            const nm = nullBy[key];
            const zeroCi = ci != null && Math.abs(ci[1] - ci[0]) < 1e-9;
            return (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <span className="text-[11.5px] text-[var(--ink-700)]">{subZh}</span>
                <span className="font-mono text-[11px] text-[var(--text-dim)]">
                  {detail[key] == null ? "—" : Number(detail[key]).toFixed(3)}
                  {ci
                    ? zeroCi
                      ? " CI 不可用"
                      : ` CI [${ci[0]?.toFixed(2)}, ${ci[1]?.toFixed(2)}]`
                    : ""}
                  {nm != null ? ` 随机 ${Number(nm).toFixed(3)}` : ""}
                  {pv != null ? ` p=${Number(pv).toFixed(3)}` : ""}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 简单异步加载 hook：loading / error / data 三态，错误不伪装成空数据 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<{ loading: boolean; error: string | null; data: T | null }>(
    { loading: true, error: null, data: null },
  );
  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, data: null });
    fn()
      .then((d) => { if (!cancelled) setState({ loading: false, error: null, data: d }); })
      .catch((e) => { if (!cancelled) setState({ loading: false, error: String(e), data: null }); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
