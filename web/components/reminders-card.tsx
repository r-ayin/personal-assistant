"use client";

import { motion } from "framer-motion";
import { CountdownRing, Tag } from "@/components/ui";
import { pick, RECURRING_LABELS } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { Reminder } from "@/lib/types";

/** 兼容 "YYYY-MM-DD HH:mm" 与 ISO "YYYY-MM-DDTHH:mm"（空格形式 Safari 无法直接解析） */
export function parseDt(s?: string): number {
  if (!s) return NaN;
  return new Date(s.trim().replace(" ", "T")).getTime();
}

/**
 * 倒计时环比例：剩余时间 / 「创建 → 到期」区间。
 * 已过期 → 0；无 created_at 时用 24h 窗口估算。
 */
export function dueFraction(r: Reminder, now: number): number {
  const due = parseDt(r.when_dt);
  if (Number.isNaN(due)) return 0;
  const remaining = due - now;
  if (remaining <= 0) return 0;
  const created = parseDt(r.created_at);
  const total = !Number.isNaN(created) && due > created ? due - created : 24 * 60 * 60 * 1000;
  return Math.min(1, remaining / total);
}

/** 剩余时间的中文低语 */
export function remainText(r: Reminder, now: number): string {
  const due = parseDt(r.when_dt);
  if (Number.isNaN(due)) return "时间未定";
  const ms = due - now;
  if (ms <= 0) return "已到期";
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return "转瞬即至";
  if (minutes < 60) return `还剩 ${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `还剩 ${hours} 小时`;
  const days = Math.floor(hours / 24);
  return `还剩 ${days} 天`;
}

/** "2026-09-01 21:30" / ISO → "09-01 21:30"（等宽展示） */
function fmtTime(s?: string): string {
  return (s || "").slice(0, 16).replace("T", " ").replace(/^(\d{4})-(\d{2})-(\d{2})/, "$2-$3");
}

/** 一张提醒卡：余烬倒计时环 + 内容 + 循环周期 chip；已燃尽的安静退场 */
export default function ReminderCard({
  reminder,
  now,
  index,
}: {
  reminder: Reminder;
  now: number;
  index: number;
}) {
  const fraction = dueFraction(reminder, now);
  const expired = fraction <= 0;
  return (
    <motion.article
      className="glass-card p-5 flex items-center gap-5"
      initial={{ opacity: 0, y: 28 }}
      animate={{ opacity: expired ? 0.66 : 1, y: 0 }}
      transition={{ delay: 0.15 + index * 0.06, duration: 0.8, ease: EASE.out }}
    >
      <CountdownRing fraction={fraction} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{reminder.what}</div>
        <div
          className="text-xs mt-1.5"
          style={{
            fontFamily: "var(--font-mono)",
            color: expired ? "var(--text-weak)" : "var(--ochre)",
          }}
        >
          {fmtTime(reminder.when_dt)} · {remainText(reminder, now)}
        </div>
        {(reminder.recurring || reminder.fired === 1) && (
          <div className="flex flex-wrap gap-2 mt-2.5">
            {reminder.recurring && (
              <Tag color="ochre">{pick(RECURRING_LABELS, reminder.recurring)}</Tag>
            )}
            {reminder.fired === 1 && <Tag color="cinnabar">已燃尽</Tag>}
          </div>
        )}
      </div>
    </motion.article>
  );
}
