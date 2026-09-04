import type { Transition, Variants } from "framer-motion";

/**
 * 动效系统单一真源 —— 合约见 design-system/DESIGN.md「生长与断裂」。
 *
 * 取代原先在 8 个文件里各自复制的 `EASE_SOFT = [0.22,1,0.36,1]`。
 *
 * 铁律：**任何入场动效都不得让元素在动画不驱动时不可见**。
 * 旧实现用 `initial={{opacity:0}}` 包住全部 11 个页面，rAF 不驱动的环境下
 * 整站全白。新实现一律经 components/Reveal.tsx，它在 prefers-reduced-motion
 * 或动效不可用时直接渲染静态可见元素；globals.css 另有一层 !important 兜底。
 */

/** 缓动曲线 */
export const EASE = {
  /** 长尾缓出：安静收束，用于大面积位移 */
  out: [0.22, 1, 0.36, 1] as const,
  /** 强过冲：激进入场，末端回弹 */
  overshoot: [0.34, 1.56, 0.64, 1] as const,
  /** 急入急出：tab 切换、路由转场 */
  snap: [0.65, 0, 0.35, 1] as const,
  /** 墨迹渗透：先滞后进骤然扩散 */
  ink: [0.16, 0.84, 0.24, 1] as const,
};

/** spring 预设。旧合约禁 spring，新合约放开——过冲与回弹是"激进"的主要来源。 */
export const SPRING = {
  bouncy: { type: "spring", stiffness: 420, damping: 18, mass: 0.9 },
  stiff: { type: "spring", stiffness: 620, damping: 32 },
  soft: { type: "spring", stiffness: 180, damping: 26 },
  rubber: { type: "spring", stiffness: 900, damping: 14, mass: 0.6 },
} satisfies Record<string, Transition>;

/** 时长（秒） */
export const DUR = { fast: 0.18, base: 0.34, slow: 0.62, glacial: 1.2 };

/** 交错延迟。快速交错（30~60ms）配合过冲曲线制造"生长"感。 */
export function staggerDelay(i: number, step = 0.045, base = 0): number {
  return base + i * step;
}

/** 容器/子项交错对，配合 AnimatePresence 使用 */
export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045, delayChildren: 0.06 } },
};

/** 上升入场：位移 + 轻微缩放 + 去模糊 */
export const rise: Variants = {
  // 性能：不用 filter blur——动画 blur 每帧全块模糊，软件光栅下极贵。
  // 入场观感由 opacity + 位移 + 微缩放承担。
  hidden: { opacity: 0, y: 26, scale: 0.985 },
  show: {
    opacity: 1, y: 0, scale: 1,
    transition: { duration: DUR.slow, ease: EASE.out },
  },
};

/** 墨滴渗透：从极小骤然铺开，末端过冲 */
export const inkSpread: Variants = {
  // 性能：不用 filter blur；"墨滴铺开"观感由 borderRadius 形变 + 缩放承担。
  hidden: { opacity: 0, scale: 0.6, borderRadius: "48%" },
  show: {
    opacity: 1, scale: 1, borderRadius: "20px",
    transition: { duration: 0.72, ease: EASE.ink },
  },
};

/** 从侧面切入，带强过冲 */
export const slideOvershoot: Variants = {
  hidden: { opacity: 0, x: -34 },
  show: {
    opacity: 1, x: 0,
    transition: { duration: 0.5, ease: EASE.overshoot },
  },
};

/** 年轮绘制：SVG 描边自生长。配合 motion.circle/motion.path 的 pathLength。 */
export const ringDraw = (duration = 1.4, delay = 0): Transition => ({
  duration,
  delay,
  ease: EASE.out,
});

export const RING_HIDDEN = { pathLength: 0, opacity: 0 } as const;
export const RING_SHOW = { pathLength: 1, opacity: 1 } as const;

/** tab 切换转场：横向推移 + 淡出，方向由 `dir` 决定 */
export function tabVariants(dir: 1 | -1): Variants {
  return {
    enter: { opacity: 0, x: dir * 42, scale: 0.99 },
    center: {
      opacity: 1, x: 0, scale: 1,
      transition: { duration: DUR.base, ease: EASE.snap },
    },
    exit: {
      opacity: 0, x: dir * -42, scale: 0.99,
      transition: { duration: DUR.fast, ease: EASE.snap },
    },
  };
}

/** 逐字揭示（动力排版）。注意：只对非渐变文字使用——子元素带 transform/filter
 *  会打断父级 background-clip:text，导致整段标题隐形（旧 TitleStagger 的教训）。
 *  性能：不用 3D rotateX——每字一个 3D 合成层在软件光栅下极贵（首帧 3.1s→8.7s
 *  的主因之一），标题字号下 rotateX 视觉增益很小；2D 位移+opacity 配 bouncy
 *  spring 保留逐字弹入观感。 */
export const charReveal: Variants = {
  hidden: { opacity: 0, y: "0.55em" },
  show: { opacity: 1, y: 0, transition: { ...SPRING.bouncy } },
};
