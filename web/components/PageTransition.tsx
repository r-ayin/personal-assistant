"use client";

import { motion, useReducedMotion } from "framer-motion";
import { RevealGroup, RevealItem } from "@/components/Reveal";
import { charReveal, DUR, EASE } from "@/lib/motion";

interface Props {
  children: React.ReactNode;
  title?: string;
  /** 标题右侧元信息（计数、时间戳、操作按钮） */
  meta?: React.ReactNode;
  /** 副标题：一行衬线小字，承接旧的 WhisperLine 语义 */
  subtitle?: string;
}

/**
 * 标题逐字揭示（动力排版）。安全前提：.pa-title 是实色墨 + 朱砂下划线，
 * 不是 background-clip:text 渐变——子元素带 transform 才不会打断裁剪（旧
 * TitleStagger 的教训）。rotateX 需要父级 perspective。
 * 经 RevealGroup/RevealItem 走全站唯一的淡入入口：reduced-motion 或动画
 * 停摆（1.4s 兜底）时改渲染静态标题，可见性铁律不破。
 */
function TitleChars({ title }: { title: string }) {
  return (
    <RevealGroup
      as="h1"
      className="pa-title text-[34px] leading-tight"
      style={{ perspective: 600 }}
      step={0.038}
      base={0.05}
    >
      {Array.from(title).map((ch, i) => (
        <RevealItem key={`${i}-${ch}`} as="span" className="char-span" variant={charReveal}>
          {ch}
        </RevealItem>
      ))}
    </RevealGroup>
  );
}

/**
 * 页面外壳：统一的 padding 与最大宽度由 .pa-page 承担，标题在其内部与内容对齐。
 *
 * 两处与旧实现的关键差异：
 *  1. 不再用 `initial={{opacity:0}}` 做入场门控 —— 旧写法包住全部 11 页，
 *     rAF 不驱动时整站全白。现在容器只做极轻位移，reduced-motion 下完全不挂 motion。
 *  2. 标题不再渲染在页面的 max-width 容器之外（旧实现导致标题贴左边缘、
 *     内容居中，视觉不对齐）。
 *
 * 迁入 tab 的旧页面要**去掉自己的 `max-w-[1200px] mx-auto px-8` 外层 div**，
 * 否则与本组件的 .pa-page 双重内边距。
 */
export default function PageTransition({ children, title, meta, subtitle }: Props) {
  const reduced = useReducedMotion();

  const body = (
    <>
      {title && (
        <header className="mb-9">
          <div className="flex items-end justify-between gap-6 flex-wrap">
            {reduced
              ? <h1 className="pa-title text-[34px] leading-tight">{title}</h1>
              : <TitleChars title={title} />}
            {meta && (
              <div className="pb-2 font-mono text-[12px] tracking-wide text-[var(--text-dim)]">
                {meta}
              </div>
            )}
          </div>
          {subtitle && (
            <p className="mt-3 font-serif text-[14px] leading-relaxed text-[var(--text-weak)]">
              {subtitle}
            </p>
          )}
        </header>
      )}
      {children}
    </>
  );

  if (reduced) return <div className="pa-page">{body}</div>;

  return (
    <motion.div
      className="pa-page"
      initial={{ y: 12 }}
      animate={{ y: 0 }}
      transition={{ duration: DUR.slow, ease: EASE.out }}
    >
      {body}
    </motion.div>
  );
}

/** 兼容旧导入：标题可见性现在完全由 CSS 的 .pa-title 保证，不依赖 JS 动画 */
export function TitleStagger({ title }: { title: string }) {
  return <h1 className="pa-title text-[34px] mb-8">{title}</h1>;
}
