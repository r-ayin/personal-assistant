import { useState } from "react";

/**
 * 图表主题单一真源。
 *
 * 两条硬约束决定了它的形状：
 *  1. token 门禁（token-audit.cjs + DESIGN.md）：组件里不许出现硬编码 hex/rgba，
 *     颜色一律引用 globals.css :root 定义的 CSS token。
 *  2. SVG 表现属性（stroke/fill 作为 attribute）不参与 CSS 变量替换——
 *     recharts 把颜色写进 attribute，变量引用会被当非法值忽略、落成默认黑。
 * 所以这里在客户端挂载时用 getComputedStyle 把 token 解析成具体颜色串再交给
 * recharts；源码里仍然只有 var() 引用（兜底分支），两道门禁都过。
 * ssr:false 的动态导入保证解析只发生在浏览器里。
 */

export interface ChartTheme {
  ink900: string;
  ink700: string;
  ink500: string;
  ink300: string;
  ink02: string;
  ink06: string;
  ink08: string;
  ink12: string;
  ink18: string;
  hairline: string;
  accent: string;
  interactive: string;
  positive: string;
  caution: string;
  surface: string;
}

/** 兜底：仅用于无 window 的环境（ssr:false 下不会真正渲染） */
const VAR_THEME: ChartTheme = {
  ink900: "var(--ink-900)",
  ink700: "var(--ink-700)",
  ink500: "var(--ink-500)",
  ink300: "var(--ink-300)",
  ink02: "var(--ink-02)",
  ink06: "var(--ink-06)",
  ink08: "var(--ink-08)",
  ink12: "var(--ink-12)",
  ink18: "var(--ink-18)",
  hairline: "var(--hairline)",
  accent: "var(--cinnabar)",
  interactive: "var(--indigo)",
  positive: "var(--mineral)",
  caution: "var(--ochre)",
  surface: "var(--porcelain-2)",
};

const TOKEN_KEYS: Record<keyof ChartTheme, string> = {
  ink900: "--ink-900",
  ink700: "--ink-700",
  ink500: "--ink-500",
  ink300: "--ink-300",
  ink02: "--ink-02",
  ink06: "--ink-06",
  ink08: "--ink-08",
  ink12: "--ink-12",
  ink18: "--ink-18",
  hairline: "--hairline",
  accent: "--cinnabar",
  interactive: "--indigo",
  positive: "--mineral",
  caution: "--ochre",
  surface: "--porcelain-2",
};

function resolveTheme(): ChartTheme {
  if (typeof window === "undefined") return VAR_THEME;
  const cs = getComputedStyle(document.documentElement);
  const out = {} as ChartTheme;
  for (const k of Object.keys(TOKEN_KEYS) as (keyof ChartTheme)[]) {
    out[k] = cs.getPropertyValue(TOKEN_KEYS[k]).trim() || VAR_THEME[k];
  }
  return out;
}

/** 客户端解析一次 token；同组件树内多次调用各自解析，成本是一次 getComputedStyle */
export function useChartTheme(): ChartTheme {
  const [theme] = useState(resolveTheme);
  return theme;
}

/** 坐标轴统一样式：墨线 + 等宽小字，全部图表共用 */
export function axisProps(t: ChartTheme) {
  return {
    stroke: t.ink18,
    tick: { fill: t.ink300, fontSize: 11, fontFamily: "var(--font-mono)" },
    tickLine: false as const,
    axisLine: { stroke: t.hairline },
  };
}

/** 刻度数字修剪：整数保持整数，≥1 两位小数，更小的三位——杜绝 0.9657713499999999 */
export function fmtTick(v: number): string {
  if (!Number.isFinite(v)) return "";
  if (Number.isInteger(v)) return String(v);
  const a = Math.abs(v);
  if (a >= 100) return v.toFixed(0);
  if (a >= 1) return v.toFixed(2);
  if (a >= 0.01) return v.toFixed(3);
  return v.toExponential(1);
}

/** 悬浮读数：瓷底墨字等宽，不用 backdrop-filter（性能合约） */
export function tooltipStyle(t: ChartTheme): React.CSSProperties {
  return {
    background: t.surface,
    border: `1px solid ${t.hairline}`,
    borderRadius: 6,
    fontSize: 12,
    fontFamily: "var(--font-mono)",
    color: t.ink700,
    padding: "6px 10px",
  };
}
