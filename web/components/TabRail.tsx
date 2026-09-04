"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import type { TabDef } from "@/lib/nav";
import { SPRING, tabVariants } from "@/lib/motion";

/**
 * 二级 tab 条。激活态底部的朱砂游标用 layoutId 在 tab 之间滑动——
 * 这是"精致动效"的主要落点之一：游标带轻微过冲地拉伸、移动、回弹。
 */
export default function TabRail({
  tabs, active, onChange,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (id: string) => void;
}) {
  const reduced = useReducedMotion();
  if (!tabs.length) return null;

  return (
    <div className="tab-rail" role="tablist" aria-label="二级导航">
      {tabs.map((t) => {
        const Icon = t.icon;
        const on = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={on}
            aria-controls={`panel-${t.id}`}
            onClick={() => onChange(t.id)}
            className={`tab-item ${on ? "is-active" : ""}`}
          >
            <Icon size={14} strokeWidth={on ? 2.2 : 1.6} />
            <span>{t.label}</span>
            {on && (
              reduced
                ? <span className="tab-ink" />
                : (
                  <motion.span
                    className="tab-ink"
                    layoutId="tab-ink"
                    transition={SPRING.bouncy}
                  />
                )
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * tab 面板转场。方向由 useTab 给出，横向推移 + 淡出。
 * reduced-motion 下直接渲染静态内容，不做任何位移与透明度动画。
 */
export function TabPanel({
  id, dir, children,
}: {
  id: string;
  dir: 1 | -1;
  children: ReactNode;
}) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <div id={`panel-${id}`} role="tabpanel">{children}</div>;
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={id}
        id={`panel-${id}`}
        role="tabpanel"
        variants={tabVariants(dir)}
        initial="enter"
        animate="center"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
