"use client";

import {
  Bar, BarChart, Cell, Line, LineChart, ResponsiveContainer, XAxis, YAxis,
} from "recharts";
import { axisProps, useChartTheme } from "./theme";
import { useChartMotion } from "./useChartMotion";

export interface GrowthPoint {
  window: string;
  proxy_score: number;
  evidence_count?: number;
}

/**
 * Ryff 六维成长代理分。score_history 是窗口序列；当前实现只有 "all" 单窗口，
 * 单点画不成趋势——如实标注"单窗口，无趋势可言"，不插值不 extrapolate。
 */
export default function GrowthChart({ history, label }: {
  history: GrowthPoint[];
  label: string;
}) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const pts = (history ?? []).filter((h) => typeof h?.proxy_score === "number");
  if (!pts.length) return null;

  if (pts.length === 1) {
    const v = Math.max(0, Math.min(1, pts[0].proxy_score));
    return (
      <div className="mt-1">
        <div className="relative h-[6px] rounded-full bg-[var(--ink-06)]">
          <div
            className="absolute left-0 top-0 h-full rounded-full"
            style={{ width: `${v * 100}%`, background: t.interactive }}
          />
        </div>
        <p className="mt-1 text-[10.5px] text-[var(--text-weak)]">
          {label}：代理分 {v.toFixed(2)}（单窗口 all，无趋势可言；证据 {pts[0].evidence_count ?? 0} 条）
        </p>
      </div>
    );
  }

  const data = pts.map((p, i) => ({ w: p.window || `w${i + 1}`, v: p.proxy_score }));
  return (
    <div className="mt-1" style={{ height: 72 }}>
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -26 }}>
          <XAxis dataKey="w" {...axisProps(t)} />
          <YAxis domain={[0, 1]} {...axisProps(t)} />
          <Line type="monotone" dataKey="v" stroke={t.interactive} strokeWidth={1.5}
            dot={{ r: 2.5, fill: t.accent, strokeWidth: 0 }}
            isAnimationActive={anim} animationDuration={dur} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 情感剖面五量：正/负均值、波动 MSSD、惯性、粒度 */
export function AffectBars({ a }: { a: {
  pa_mean: number | null; na_mean: number | null; variability_mssd: number | null;
  inertia: number | null; granularity: number | null;
} }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const rows: [string, number | null, string][] = [
    ["正向均值", a.pa_mean, "正向情绪的平均强度"],
    ["负向均值", a.na_mean, "负向情绪的平均强度"],
    ["波动 MSSD", a.variability_mssd, "相邻两次情绪的均方逐次差：情绪摆幅"],
    ["惯性", a.inertia, "lag-1 自相关：情绪自我延续的强度（Kuppens 2010）"],
    ["粒度", a.granularity, "情绪标签分布熵：能把感受分辨得多细"],
  ];
  const data = rows.map(([k, v]) => ({ k, v: v ?? 0 }));
  return (
    <div className="mt-2">
      <div style={{ height: 150 }} className="w-full">
        <ResponsiveContainer width="100%" height="100%" debounce={80}>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -22 }}>
            <XAxis dataKey="k" {...axisProps(t)} />
            <YAxis {...axisProps(t)} />
            <Bar dataKey="v" isAnimationActive={anim} animationDuration={dur} radius={[2, 2, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={i === 0 ? t.positive : i === 1 ? t.accent : t.interactive} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-1 space-y-0.5 text-[10.5px] leading-relaxed text-[var(--text-weak)]">
        {rows.map(([k, , d]) => <li key={k}>{k}：{d}</li>)}
      </ul>
    </div>
  );
}
