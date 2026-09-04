"use client";

import { useEffect, useState } from "react";
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

/** 特质分布条：mean±sd，标 n 与是否升格；未升格视觉弱化 */
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
            : `${mean >= 0 ? "+" : ""}${mean.toFixed(2)} ± ${(sd ?? 0).toFixed(2)} · n=${d?.n_observations ?? 0} · 会话${t.n_independent_conv}`}
        </span>
      </div>
      <div className="relative mt-1 h-[6px] rounded-full bg-[var(--ink-06)]">
        <div className="absolute top-0 h-full rounded-full bg-[var(--ink-18)]"
          style={{ left: `${Math.max(0, pos - width / 2)}%`, width: `${width}%` }} />
        <div className="absolute top-[-2px] h-[10px] w-[2px] bg-[var(--cinnabar)]"
          style={{ left: `${pos}%` }} />
      </div>
      <p className="mt-1 text-[11px] text-[var(--text-weak)]">
        {promoted
          ? t.is_proxy === 1 ? "代理推断，非量表实测" : ""
          : `独立会话 ${t.n_independent_conv}/3，未升格为稳定特质`}
      </p>
    </div>
  );
}

/** 指标行：value + CI + n；eligible=0 灰显并给理由 */
export function MetricRow({ m }: { m: PortraitMetricRow }) {
  const ok = m.eligible === 1;
  return (
    <div className={`flex items-baseline justify-between gap-4 py-2 border-b border-[var(--hairline)] ${ok ? "" : "opacity-45"}`}>
      <div className="min-w-0">
        <span className="text-[13px] text-[var(--ink-700)]">{m.name}</span>
        <span className="ml-2 font-mono text-[11px] text-[var(--text-weak)]">
          {m.subject_kind}/{m.subject_id.slice(0, 18)}
        </span>
      </div>
      <div className="shrink-0 text-right font-mono text-[12px]">
        {ok ? (
          <span className="text-[var(--ink-900)]">
            {m.value == null ? "—" : m.value.toFixed(3)}
            <span className="text-[var(--text-weak)]">
              {" "}[{m.ci_low?.toFixed(2) ?? "—"}, {m.ci_high?.toFixed(2) ?? "—"}] n={m.n ?? 0}
            </span>
          </span>
        ) : (
          <span className="text-[var(--text-weak)]">{m.ineligible_reason || "样本不足"}</span>
        )}
      </div>
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
