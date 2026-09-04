"use client";

import { motion, useReducedMotion } from "framer-motion";
import { EASE, RING_HIDDEN, RING_SHOW, ringDraw, SPRING } from "@/lib/motion";

/**
 * 年轮核（今天页核心）：SVG 同心环 pathLength 0→1 自内向外逐圈画出（v4 动效语汇 #3），
 * 环数 = 记忆年数（数据驱动，见 TodayNowPanel 的 memoryYears），
 * 每第 7 环加粗——标记年（气候异常年形成的深色环）。
 * 中央计数逐位 spring 弹入（动力排版）。
 *
 * reduced-motion：直接渲染全画静态环与静态数字（第三层降级）。
 */

const SIZE = 168;
const CX = SIZE / 2;
const R_INNER = 27;
const R_STEP = 7;
const MAX_RINGS = 8;

/** 逐位弹入的等宽计数 */
function DigitRoll({ value, size }: { value: string; size: number }) {
  const reduced = useReducedMotion();
  const chars = Array.from(value);
  if (reduced) {
    return (
      <span className="ring-core-count" style={{ fontSize: size }}>
        {value}
      </span>
    );
  }
  return (
    <motion.span
      className="ring-core-count"
      style={{ fontSize: size }}
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: 0.5 } } }}
    >
      {chars.map((ch, i) => (
        <motion.span
          key={`${i}-${ch}`}
          className="char-span"
          variants={{
            hidden: { opacity: 0, y: 22, scale: 0.4 },
            show: { opacity: 1, y: 0, scale: 1, transition: { ...SPRING.bouncy } },
          }}
        >
          {ch}
        </motion.span>
      ))}
    </motion.span>
  );
}

export default function RingCore({
  years,
  count,
  countLabel,
}: {
  /** 记忆年数 = 环数（1~8，超出封顶） */
  years: number;
  /** 中央计数（记忆总数）；null 时显示破折号 */
  count: number | null;
  countLabel?: string;
}) {
  const reduced = useReducedMotion();
  const rings = Math.max(1, Math.min(years, MAX_RINGS));
  const radii = Array.from({ length: rings }, (_, i) => R_INNER + i * R_STEP);
  const text = count === null ? "—" : String(count);

  return (
    <div
      className="ring-core"
      role="img"
      aria-label={countLabel ?? `${rings} 圈年轮，${text} 段记忆`}
    >
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} aria-hidden="true">
        {radii.map((r, i) => {
          const marker = (i + 1) % 7 === 0;
          const cls = marker ? "is-marker" : undefined;
          return reduced ? (
            <circle key={r} cx={CX} cy={CX} r={r} className={cls} />
          ) : (
            <motion.circle
              key={r}
              cx={CX}
              cy={CX}
              r={r}
              className={cls}
              initial={RING_HIDDEN}
              animate={RING_SHOW}
              transition={ringDraw(0.95, 0.18 + i * 0.16)}
            />
          );
        })}
        {/* 髓心：中央一点朱砂，年轮从这里长出来 */}
        {reduced ? (
          <circle cx={CX} cy={CX} r={3} fill="var(--cinnabar)" stroke="none" />
        ) : (
          <motion.circle
            cx={CX}
            cy={CX}
            fill="var(--cinnabar)"
            stroke="none"
            initial={{ r: 0, opacity: 0 }}
            animate={{ r: 3, opacity: 1 }}
            transition={{ duration: 0.5, ease: EASE.overshoot }}
          />
        )}
      </svg>
      <DigitRoll value={text} size={26} />
    </div>
  );
}
