"use client";

import { useMemo } from "react";
import {
  Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis,
} from "recharts";
import type { TraitDist } from "@/lib/types";
import { axisProps, useChartTheme } from "./theme";
import { useChartMotion } from "./useChartMotion";

const normPdf = (z: number) => Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI);
function normCdf(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}
/** 偏正态分布的偏度 → δ（单调，二分求解） */
function skewOf(delta: number): number {
  const s = delta * Math.sqrt(2 / Math.PI);
  const den = 1 - s * s;
  return den <= 0 ? Math.sign(delta) : ((4 - Math.PI) / 2) * (s ** 3) / (den ** 1.5);
}
function deltaForSkew(target: number): number {
  let lo = -0.999, hi = 0.999;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (skewOf(mid) < target) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

/**
 * 特质密度分布：trait 存的不是标签而是 (mean, sd, skew) 的分布参数
 * （Whole Trait Theory：特质是密度分布，单次行为是它的一次抽样）。
 * n_observations=0 时 mean=0/sd=1 是**先验起点不是测量结果**——绝不画成曲线，
 * 只画一条虚线基线并写明"无观测数据"，否则会把"没数据"读成"测出来是 0"。
 */
export default function TraitDensityChart({ dist, promoted, isProxy, nConv }: {
  dist: TraitDist | null;
  promoted: boolean;
  isProxy: boolean;
  nConv: number;
}) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const n = dist?.n_observations ?? 0;
  const mean = dist?.mean;
  const sd = dist?.sd;

  const curve = useMemo(() => {
    if (mean == null || sd == null || sd <= 1e-6 || n < 1) return null;
    const delta = deltaForSkew(Math.max(-0.95, Math.min(0.95, dist?.skew ?? 0)));
    const alpha = delta / Math.sqrt(Math.max(1e-6, 1 - delta * delta));
    const pts: { x: number; y: number }[] = [];
    for (let i = 0; i <= 80; i++) {
      const x = -1 + (2 * i) / 80;
      const z = (x - mean) / sd;
      pts.push({ x, y: (2 / sd) * normPdf(z) * normCdf(alpha * z) });
    }
    return pts;
  }, [mean, sd, dist?.skew, n]);

  if (!curve) {
    return (
      <div className="mt-2 rounded-md bg-[var(--ink-02)] px-3 py-2">
        <div className="relative h-6">
          <div className="absolute left-0 right-0 top-1/2 border-t border-dashed border-[var(--ink-18)]" />
        </div>
        <p className="text-[10.5px] leading-relaxed text-[var(--text-weak)]">
          纯先验 · 无观测数据：mean=0 / sd=1 是贝叶斯更新的起点，不是测量结果。
          等抽取层在该维度攒到带方向的证据后，这里才会长出曲线。
        </p>
      </div>
    );
  }

  return (
    <div className={`mt-2 rounded-md bg-[var(--ink-02)] p-2 ${promoted ? "" : "opacity-70"}`}>
      <div style={{ height: 84 }} className="w-full">
        <ResponsiveContainer width="100%" height="100%" debounce={80}>
          <AreaChart data={curve} margin={{ top: 6, right: 6, bottom: 0, left: 6 }}>
            <XAxis
              dataKey="x" type="number" domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]}
              {...axisProps(t)} tickFormatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
            />
            <YAxis hide domain={[0, "dataMax"]} />
            <ReferenceLine x={0} stroke={t.hairline} />
            <ReferenceLine x={mean} stroke={t.accent} strokeWidth={1.5} />
            <Area
              type="basis" dataKey="y" stroke={t.ink700} strokeWidth={1.2}
              fill={t.ink08} isAnimationActive={anim} animationDuration={dur}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--text-weak)]">
        朱砂线=分布均值（横轴 −1 负向 … +1 正向）；曲线宽窄=sd，歪向=skew。
        观测 {n} 次 · 独立会话 {nConv}/3{promoted ? "（已升格为稳定特质）" : "（未升格）"}
        {isProxy ? " · 行为代理推断，非量表实测" : ""}。
      </p>
    </div>
  );
}
