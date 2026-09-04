"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { WikiPage } from "@/lib/types";
import { EASE } from "@/lib/motion";

const W = 760;
const H = 380;
const CX = W / 2;
const CY = H / 2;
const RX = 250;
const RY = 118;
const MAX_NODES = 8;

function shortTitle(t: string): string {
  const s = (t || "").trim();
  if (!s) return "未命名";
  return s.length > 9 ? `${s.slice(0, 9)}…` : s;
}

/**
 * 关系图：选中的知识页居中（靛青脉冲），link_ids 指向的页环绕（朱砂/石绿交替），
 * 细曲线相连——边线用 pathLength 0→1 自生长（亮底上的"墨线自画"，v4 动效语汇 #3）。
 */
export default function WikiMyceliumGraph({
  page,
  linked,
  onSelect,
}: {
  page: WikiPage;
  linked: WikiPage[];
  onSelect?: (id: string) => void;
}) {
  const reduce = useReducedMotion();
  const nodes = linked.slice(0, MAX_NODES);
  const n = nodes.length;

  const points = nodes.map((p, i) => {
    const angle = n === 1 ? 0 : -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const x = CX + RX * Math.cos(angle);
    const y = CY + RY * Math.sin(angle);
    // 细曲线：控制点向外微弯，像墨线自然弓起
    const mx = (CX + x) / 2;
    const my = (CY + y) / 2;
    const dx = mx - CX;
    const dy = my - CY;
    const len = Math.hypot(dx, dy) || 1;
    const qx = mx + (dx / len) * 30;
    const qy = my + (dy / len) * 30;
    return { p, x, y, d: `M ${CX} ${CY} Q ${qx} ${qy} ${x} ${y}` };
  });

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto"
      role="img"
      aria-label={`「${page.title}」的关系图`}
    >
      {/* 墨线自画：边线 pathLength 0→1 从中心向外生长（reduced-motion 下 framer 直接落终态） */}
      {points.map(({ p, d }, i) => (
        <motion.path
          key={`e-${p.id}`}
          d={d}
          fill="none"
          stroke="var(--hairline-strong)"
          strokeWidth={1.2}
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 0.8 }}
          transition={{ delay: 0.15 + i * 0.07, duration: 0.9, ease: EASE.out }}
        />
      ))}

      {/* 环绕节点：朱砂 / 石绿交替，点击可跳转选中 */}
      {points.map(({ p, x, y }, i) => {
        const fill = i % 2 === 0 ? "var(--cinnabar)" : "var(--mineral)";
        const ring = i % 2 === 0 ? "var(--cin-28)" : "var(--min-30)";
        return (
          <motion.g
            key={`n-${p.id}`}
            style={{ cursor: onSelect ? "pointer" : undefined }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 + i * 0.07, duration: 0.7, ease: EASE.out }}
            onClick={() => onSelect?.(p.id)}
          >
            <circle cx={x} cy={y} r={10.5} fill="none" stroke={ring} strokeWidth={1} />
            <circle cx={x} cy={y} r={6} fill={fill} opacity={0.9} />
            <text
              x={x}
              y={y + 26}
              textAnchor="middle"
              style={{ fontFamily: "var(--font-serif)", fontSize: 12, fill: "var(--text-dim)" }}
            >
              {shortTitle(p.title)}
            </text>
            <title>{p.title}</title>
          </motion.g>
        );
      })}

      {/* 中心：选中的页，靛青脉冲（reduced-motion 时省略扩散光环） */}
      {!reduce && (
        <motion.circle
          cx={CX}
          cy={CY}
          fill="none"
          stroke="var(--indigo)"
          strokeWidth={1}
          initial={{ r: 10, opacity: 0.45 }}
          animate={{ r: 26, opacity: 0 }}
          transition={{ duration: 2.6, repeat: Infinity, ease: EASE.out }}
        />
      )}
      <motion.circle
        cx={CX}
        cy={CY}
        fill="var(--indigo)"
        style={{ filter: "drop-shadow(0 0 6px var(--ind-40))" }}
        initial={{ r: 2, opacity: 0 }}
        animate={{ r: 8, opacity: 1 }}
        transition={{ duration: 0.7, ease: EASE.out }}
      />
      <motion.text
        x={CX}
        y={CY + 30}
        textAnchor="middle"
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 13,
          fontWeight: 600,
          fill: "var(--text-main)",
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.7, ease: EASE.out }}
      >
        {shortTitle(page.title)}
      </motion.text>
    </svg>
  );
}
