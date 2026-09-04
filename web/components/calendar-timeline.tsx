"use client";

import { motion } from "framer-motion";
import type { Event } from "@/lib/types";
import { speakerLabel } from "@/lib/labels";
import { EASE } from "@/lib/motion";

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

/** 本地日期 "YYYY-MM-DD" */
function localDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function weekdayOf(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  if (Number.isNaN(d.getTime())) return "";
  return `星期${WEEKDAYS[d.getDay()]}`;
}

export interface DayGroup {
  day: string;
  events: Event[];
}

/**
 * 竖向时间线：每日一枚暖金节点光点，左侧发丝线串联；
 * 事件卡挂在线侧，仅「今天」的节点带微光（控制同屏发光数）。
 */
export default function CalendarTimeline({ groups }: { groups: DayGroup[] }) {
  const today = localDay(new Date());
  return (
    <div>
      {groups.map((group, gi) => {
        const isToday = group.day === today;
        return (
          <motion.section
            key={group.day}
            className="relative pl-9 pb-12"
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: gi * 0.08, duration: 0.8, ease: EASE.out }}
          >
            {/* 串联发丝线 */}
            <span
              aria-hidden
              className="absolute top-5 bottom-0 w-px"
              style={{ left: 7, background: "var(--ind-16)" }}
            />
            {/* 节点：今日盖朱砂印（硬边落印环），其余安静靛青 */}
            <span
              aria-hidden
              className="absolute rounded-full"
              style={{
                left: 0,
                top: 4,
                width: 15,
                height: 15,
                background: isToday ? "var(--cinnabar)" : "var(--indigo)",
                opacity: isToday ? 1 : 0.45,
                boxShadow: isToday ? "0 0 0 3px var(--cin-12)" : undefined,
              }}
            />
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-4">
              <span
                className="text-sm font-medium"
                style={{ fontFamily: "var(--font-mono)", color: "var(--indigo)" }}
              >
                {group.day}
              </span>
              <span className="text-xs" style={{ color: "var(--text-weak)" }}>
                {weekdayOf(group.day)} · {group.events.length} 段时光
              </span>
            </div>
            <div className="space-y-3">
              {group.events.map((ev, i) => (
                <motion.div
                  key={ev.id}
                  className="glass-card p-4"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: gi * 0.08 + 0.1 + i * 0.05, duration: 0.7, ease: EASE.out }}
                >
                  <div className="flex justify-between items-start gap-4">
                    <span className="text-sm font-medium min-w-0">{ev.title}</span>
                    <span
                      className="text-xs shrink-0"
                      style={{ fontFamily: "var(--font-mono)", color: "var(--text-weak)" }}
                    >
                      {(ev.when_dt || "").slice(11, 16)}
                    </span>
                  </div>
                  {(ev.who || ev.where) && (
                    <div className="text-xs mt-2" style={{ color: "var(--text-weak)" }}>
                      {[speakerLabel(ev.who), ev.where].filter(Boolean).join(" · ")}
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          </motion.section>
        );
      })}
    </div>
  );
}
