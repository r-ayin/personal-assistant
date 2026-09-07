"use client";

import {
  ComposedChart, ErrorBar, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Scatter, XAxis, YAxis,
} from "recharts";
import { axisProps, fmtTick, useChartTheme } from "./theme";
import { useChartMotion } from "./useChartMotion";

export interface NullBandProps {
  observed: number | null;
  ciLow?: number | null;
  ciHigh?: number | null;
  nullMean?: number | null;
  q025?: number | null;
  q975?: number | null;
  height?: number;
}

const num = (v: number | null | undefined): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

/**
 * 通用"观测 vs 你自己的随机打乱基线"森林图。
 * 复杂科学指标没有普适正常范围，唯一可靠参照是自己的置换基线：
 * 灰带 = 基线 95% 区间（q025–q975），虚线 = 基线均值，朱砂点 = 观测值，墨须 = 95% CI。
 * 观测点落在灰带外才有"结构真实存在"的资格（配合 p 值文案）。
 */
export default function NullBandChart({
  observed, ciLow, ciHigh, nullMean, q025, q975, height = 92,
}: NullBandProps) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const obs = num(observed);
  if (obs == null) return null;

  const lo0 = num(ciLow);
  const hi0 = num(ciHigh);
  const bandLo = num(q025);
  const bandHi = num(q975);
  const mean = num(nullMean);
  const zeroCi = lo0 != null && hi0 != null && Math.abs(hi0 - lo0) < 1e-9;

  const pts = [obs, lo0, hi0, bandLo, bandHi, mean].filter((v): v is number => v != null);
  if (!pts.length) return null;
  const span = Math.max(...pts) - Math.min(...pts);
  const pad = span > 1e-9 ? span * 0.15 : Math.max(Math.abs(obs) * 0.3, 0.1);
  const domain: [number, number] = [Math.min(...pts) - pad, Math.max(...pts) + pad];

  const data = [{
    v: obs,
    ci: zeroCi || lo0 == null || hi0 == null ? undefined : [obs - lo0, hi0 - obs],
  }];

  return (
    <div className="mt-2">
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%" debounce={80}>
          <ComposedChart layout="vertical" data={data} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <XAxis type="number" domain={domain} {...axisProps(t)} tickFormatter={fmtTick} />
            <YAxis type="category" dataKey={() => ""} hide />
            {bandLo != null && bandHi != null && bandLo !== bandHi && (
              <ReferenceArea x1={bandLo} x2={bandHi} fill={t.ink06} fillOpacity={1} stroke="none" />
            )}
            {mean != null && (
              <ReferenceLine x={mean} stroke={t.ink300} strokeDasharray="4 4" />
            )}
            <Scatter dataKey="v" fill={t.accent} isAnimationActive={anim} animationDuration={dur}>
              {data[0].ci && (
                <ErrorBar dataKey="ci" direction="x" width={6} strokeWidth={1.5} stroke={t.ink700} />
              )}
            </Scatter>
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--text-weak)]">
        灰带=你自己随机打乱后的 95% 基线区间　虚线=基线均值　朱砂点=观测值
        {zeroCi ? "　（该统计量对刀切不敏感，CI 须不画）" : "　墨须=95% 置信区间"}
      </p>
    </div>
  );
}
