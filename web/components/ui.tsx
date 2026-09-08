"use client";

import { motion, useReducedMotion } from "framer-motion";
import Reveal, { RevealGroup, RevealItem } from "@/components/Reveal";
import { charReveal, DUR, EASE, inkSpread } from "@/lib/motion";

/**
 * 共享 UI 原件。动效预设一律来自 lib/motion.ts（单一真源），
 * 颜色一律引用 CSS 变量 token（单一真源 app/globals.css :root）。
 */

/** v4 色名为主；v3 旧色名保留为别名兜底（调用处已全部迁移，新代码只用新名） */
export type TagColor =
  | "default" | "indigo" | "mineral" | "ochre" | "cinnabar"
  | "lumen" | "moss" | "ember" | "bloom";

/** 标签 Chips：四色语义 alpha 底，文字一律中文 */
export function Tag({ children, color = "default" }: { children: React.ReactNode; color?: TagColor }) {
  const colors: Record<string, [string, string]> = {
    default: ["var(--ink-12)", "var(--text-dim)"],
    indigo: ["var(--ind-10)", "var(--indigo-deep)"],
    mineral: ["var(--min-10)", "var(--mineral-deep)"],
    ochre: ["var(--och-10)", "var(--ochre-deep)"],
    cinnabar: ["var(--cin-10)", "var(--cinnabar-deep)"],
  };
  // v3 旧色名 → v4 语义（lumen 金=交互→靛青，moss=成功→石绿，ember=提醒→赭石，bloom=情感→朱砂）
  const alias: Record<string, string> = { lumen: "indigo", moss: "mineral", ember: "ochre", bloom: "cinnabar" };
  const [bg, fg] = colors[alias[color] ?? color] || colors.default;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium" style={{ background: bg, color: fg }}>
      {children}
    </span>
  );
}

export function SectionHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div>
        <h2 className="text-xl font-semibold" style={{ fontFamily: "var(--font-serif)" }}>{title}</h2>
        {subtitle && <p className="text-xs mt-1" style={{ color: "var(--text-weak)" }}>{subtitle}</p>}
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}

/** 薄瓷卡片：入场经 Reveal（可见性铁律），可交错 */
export function GlassCard({ children, delay = 0, className = "", style }: {
  children: React.ReactNode; delay?: number; className?: string; style?: React.CSSProperties;
}) {
  return (
    <Reveal as="section" className={`glass-card p-6 ${className}`} style={style} delay={delay}>
      {children}
    </Reveal>
  );
}

/** 加载：光点呼吸，不用转圈 */
export function LoadingDots({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-2" role="status" aria-label={label || "加载中"}>
      <span className="empty-seed-dot" style={{ width: 8, height: 8 }} />
      {label && <span className="text-[13px]" style={{ color: "var(--text-weak)" }}>{label}</span>}
    </div>
  );
}

/**
 * 逐字生长（动力排版）：每个字符经 charReveal（rotateX -52°→0 + spring 过冲）
 * 快速交错立起，像墨迹在纸上逐字显现。
 * reduced-motion / 动画停摆时由 RevealGroup 直接渲染静态全文——可见性铁律。
 * `speed` 沿用旧 API（ms/字），但整段揭示时长封顶 2.4s，长回答不会拖成分钟级。
 */
export function TypewriterText({ text, speed = 20, className = "" }: { text: string; speed?: number; className?: string }) {
  const chars = Array.from(text);
  const step = chars.length > 1 ? Math.min(speed / 1000, 2.4 / (chars.length - 1)) : 0;
  return (
    <RevealGroup as="span" className={className} step={step} style={{ perspective: 400 }}>
      {chars.map((ch, i) => (
        <RevealItem key={`${i}-${ch}`} as="span" variant={charReveal} className="char-span">
          {ch}
        </RevealItem>
      ))}
    </RevealGroup>
  );
}

/** 倒计时环：fraction ∈ [0,1]，剩余越少色越强调（靛青→赭石→朱砂） */
export function CountdownRing({ fraction, size = 64 }: { fraction: number; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, fraction));
  const color = clamped < 0.25 ? "var(--cinnabar)" : clamped < 0.6 ? "var(--ochre)" : "var(--indigo)";
  return (
    <div className="countdown-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--edge)" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r}
          stroke={color}
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - clamped) }}
          transition={{ duration: 1.2, ease: EASE.out }}
        />
      </svg>
    </div>
  );
}

/**
 * 时刻卡：一张盖了朱砂印的纸片。
 * 入场 = inkSpread（墨滴渗透：从极小骤然铺开，末端过冲）；
 * hover = 左缘印线向下"盖章"生长（globals.css .firefly-seed::after）。
 * reduced-motion 直接渲染静态卡片，不留 inline opacity。
 */
export function SeedCard({ quote, narrative, meta, delay = 0, onClick }: {
  quote: string; narrative?: string; meta?: React.ReactNode; delay?: number; onClick?: () => void;
}) {
  const reduced = useReducedMotion();
  const duration = 3 + (Math.abs(hashCode(quote)) % 50) / 10; // 3.0~8.0s 稳定伪随机
  const style = { ["--phase" as string]: `${duration}s` };

  const inner = (
    <>
      <p className="serif" style={{ fontSize: 16, lineHeight: 1.9, color: "var(--text-main)" }}>“{quote}”</p>
      {narrative && <p style={{ fontSize: 13, color: "var(--text-dim)", marginTop: 10, lineHeight: 1.8 }}>{narrative}</p>}
      {meta && <div className="flex flex-wrap items-center gap-2" style={{ marginTop: 14, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-weak)" }}>{meta}</div>}
    </>
  );

  if (reduced) {
    return <article className="firefly-seed" style={style} onClick={onClick}>{inner}</article>;
  }
  return (
    <motion.article
      className="firefly-seed"
      style={style}
      variants={inkSpread}
      initial="hidden"
      animate="show"
      transition={{ delay }}
      onClick={onClick}
    >
      {inner}
    </motion.article>
  );
}

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

/** 衬线低语行：页面顶部的一句情感化说明 */
export function WhisperLine({ children, delay = 0.3 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.p
      className="serif"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: DUR.slow, ease: EASE.out }}
      style={{ color: "var(--text-weak)", fontSize: 13, letterSpacing: "0.08em" }}
    >
      {children}
    </motion.p>
  );
}

/** 等宽计数 */
export function MonoCount({ value, size = 24, color = "var(--text-main)" }: { value: number | string; size?: number; color?: string }) {
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontSize: size, color, fontVariantNumeric: "tabular-nums" }}>
      {value}
    </span>
  );
}

/**
 * 行内 **强调** 的最小渲染器。
 * 文案数据模块（labels-zh 的 METRICS_INTRO、metrics-science 的各字段）用 **x** 标重点；
 * 直接当纯文本渲染会把星号裸奔到界面上。只认 **bold** 一种标记，其余原样输出。
 */
export function Rich({ text }: { text: string }) {
  const parts = (text ?? "").split(/\*\*([^*]+)\*\*/g);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1
          ? <strong key={i} className="font-semibold" style={{ color: "var(--ink-900)" }}>{p}</strong>
          : <span key={i}>{p}</span>,
      )}
    </>
  );
}
