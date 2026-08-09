import Link from "next/link";
import { Bell, CalendarDays, ChevronRight } from "lucide-react";
import type { Event, Reminder } from "@/lib/types";

interface TodayRailProps {
  reminders: Reminder[];
  events: Event[];
}

function displayTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "未定时间";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function TodayRail({ reminders, events }: TodayRailProps) {
  const pending = reminders.filter((item) => !item.fired).slice(0, 5);
  const upcoming = [...events]
    .sort((left, right) => left.when_dt.localeCompare(right.when_dt))
    .slice(0, 5);

  return (
    <aside className="today-rail" aria-label="今日安排">
      <section className="rail-section">
        <header>
          <span><Bell size={15} aria-hidden="true" /> 待办提醒</span>
          <Link href="/reminders/" aria-label="查看全部提醒"><ChevronRight size={16} /></Link>
        </header>
        <div className="rail-list">
          {pending.length === 0 && <p className="rail-empty">当前没有待处理提醒</p>}
          {pending.map((reminder) => (
            <article key={reminder.id} className="rail-item">
              <time>{displayTime(reminder.when_dt)}</time>
              <div><strong>{reminder.what}</strong><span>{reminder.when_raw || "已记录"}</span></div>
            </article>
          ))}
        </div>
      </section>

      <section className="rail-section">
        <header>
          <span><CalendarDays size={15} aria-hidden="true" /> 今日日程</span>
          <Link href="/calendar/" aria-label="查看完整日历"><ChevronRight size={16} /></Link>
        </header>
        <div className="rail-list">
          {upcoming.length === 0 && <p className="rail-empty">今天暂时没有日程</p>}
          {upcoming.map((event) => (
            <article key={event.id} className="rail-item">
              <time>{displayTime(event.when_dt)}</time>
              <div>
                <strong>{event.title}</strong>
                <span>{[event.who, event.where].filter(Boolean).join(" · ") || event.when_raw}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </aside>
  );
}
