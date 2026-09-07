import { useReducedMotion } from "framer-motion";

/**
 * 图表动效合约（DESIGN.md §6 第三层降级）：
 * prefers-reduced-motion 时 recharts 入场动画整体关闭、直接渲染终帧。
 * 时长 900ms 落在 0.5–1.4s 生长带；一律一次性入场，不用 animationLoop
 * （同屏频闪预算 ≤1）。
 */
export function useChartMotion(): { anim: boolean; dur: number } {
  const reduced = useReducedMotion();
  return { anim: !reduced, dur: reduced ? 0 : 900 };
}
