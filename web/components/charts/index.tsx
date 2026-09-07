"use client";

import dynamic from "next/dynamic";
import ChartSkeleton from "./ChartSkeleton";

/**
 * 图表层的唯一 chunk 边界：recharts 只允许经由此文件进入应用。
 * 全部 ssr:false —— 静态导出预渲染时 ResponsiveContainer 量到 0 宽会画空图；
 * 动态 import 让 recharts 留在异步 vendor chunk，不污染首屏（/today/ 等落地页
 * 根本不下载它），与 ScrollReveal 的 gsap 动态 import 同一合约。
 * 面板文件禁止直接 import recharts 或本目录下的具体图表文件。
 */
export const NullBandChart = dynamic(() => import("./NullBandChart"), {
  ssr: false,
  loading: () => <ChartSkeleton height={92} />,
});

export const MetricDetailChart = dynamic(() => import("./DetailCharts"), {
  ssr: false,
  loading: () => <ChartSkeleton height={150} />,
});

export const TraitDensityChart = dynamic(() => import("./TraitDensityChart"), {
  ssr: false,
  loading: () => <ChartSkeleton height={84} label="密度曲线加载中…" />,
});

export const GrowthChart = dynamic(() => import("./GrowthChart"), {
  ssr: false,
  loading: () => <ChartSkeleton height={72} label="成长曲线加载中…" />,
});

export const AffectBars = dynamic(
  () => import("./GrowthChart").then((m) => m.AffectBars),
  { ssr: false, loading: () => <ChartSkeleton height={150} label="情感剖面加载中…" /> },
);
