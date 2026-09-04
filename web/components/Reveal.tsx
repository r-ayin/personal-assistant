"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type CSSProperties, type ElementType, type ReactNode } from "react";
import type { Transition, Variants } from "framer-motion";
import { DUR, EASE, rise } from "@/lib/motion";

/**
 * 安全入场包装器 —— 全站唯一允许的"淡入"入口。
 *
 * 三层保证，确保元素在任何情况下都可见：
 *  1. prefers-reduced-motion → 渲染纯静态元素，完全不挂 motion，不留 inline opacity。
 *  2. 挂载即动画（不用 IntersectionObserver 门控）——观察者不触发就不会有元素卡在隐藏态。
 *  3. STALL_GUARD_MS 兜底：动画引擎停摆（rAF 不驱动）时，超时后**改渲染静态元素**，
 *     绕开 framer-motion 的 inline style。仅改 animate 目标无效——引擎停摆时它本来就
 *     停在 initial，必须换掉渲染路径。
 * globals.css 另有一层 @media (prefers-reduced-motion) 的 !important 复位。
 *
 * 旧实现把 `initial={{opacity:0}}` 直接写在 PageTransition 上包住全部 11 页，
 * 全站约 35 处同类写法，rAF 不驱动时整站全白。新代码禁止绕过本组件做淡入。
 */

const STALL_GUARD_MS = 1400;

/** motion 代理对象按标签名取组件；ElementType 太宽，需经 Record 收窄。 */
function motionTag(as?: ElementType) {
  const name = String(as ?? "div");
  return (motion as unknown as Record<string, typeof motion.div>)[name] ?? motion.div;
}

interface RevealProps {
  children: ReactNode;
  /** 入场变体，默认 rise */
  variant?: Variants;
  /** 交错延迟（秒） */
  delay?: number;
  className?: string;
  style?: CSSProperties;
  /** 渲染成的标签，默认 div */
  as?: ElementType;
  transition?: Transition;
  id?: string;
}

export default function Reveal({
  children, variant = rise, delay = 0, className, style, as, transition, id,
}: RevealProps) {
  const reduced = useReducedMotion();
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    if (reduced) return;
    const t = setTimeout(() => setStalled(true), STALL_GUARD_MS);
    return () => clearTimeout(t);
  }, [reduced]);

  // 保证 1 与保证 3：降级 / 停摆 → 纯静态可见元素
  if (reduced || stalled) {
    const Tag = (as ?? "div") as ElementType;
    return <Tag id={id} className={className} style={style}>{children}</Tag>;
  }

  const MotionTag = motionTag(as);
  return (
    <MotionTag
      id={id}
      className={className}
      style={style}
      variants={variant}
      initial="hidden"
      animate="show"
      transition={transition ?? { duration: DUR.slow, ease: EASE.out, delay }}
    >
      {children}
    </MotionTag>
  );
}

/**
 * 交错组：子项依次入场。子项用 RevealItem 消费同一组 variants。
 * 同样遵守"挂载即动画 + 停摆兜底"，不做滚动门控。
 */
export function RevealGroup({
  children, className, style, step = 0.045, base = 0, as,
}: {
  children: ReactNode; className?: string; style?: CSSProperties;
  step?: number; base?: number; as?: ElementType;
}) {
  const reduced = useReducedMotion();
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    if (reduced) return;
    const t = setTimeout(() => setStalled(true), STALL_GUARD_MS);
    return () => clearTimeout(t);
  }, [reduced]);

  if (reduced || stalled) {
    const Tag = (as ?? "div") as ElementType;
    return <Tag className={className} style={style}>{children}</Tag>;
  }

  const MotionTag = motionTag(as);
  return (
    <MotionTag
      className={className}
      style={style}
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: step, delayChildren: base } },
      }}
    >
      {children}
    </MotionTag>
  );
}

/** 交错组内的子项：继承父级 stagger，自身只描述 hidden/show。 */
export function RevealItem({
  children, className, style, variant = rise, as,
}: {
  children: ReactNode; className?: string; style?: CSSProperties;
  variant?: Variants; as?: ElementType;
}) {
  const reduced = useReducedMotion();
  if (reduced) {
    const Tag = (as ?? "div") as ElementType;
    return <Tag className={className} style={style}>{children}</Tag>;
  }
  const MotionTag = motionTag(as);
  return (
    <MotionTag className={className} style={style} variants={variant}>
      {children}
    </MotionTag>
  );
}
