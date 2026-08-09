"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, SourceChip, Empty } from "@/components/ui";

export default function CalendarPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [live, setLive] = useState<any[] | null>(null);

  useEffect(() => {
    (async () => {
      const res = await api.events();
      setEvents(res?.events || []);
    })();
  }, []);

  useEffect(() => {
    if (!q.trim()) {
      setLive(null);
      return;
    }
    const t = setTimeout(async () => {
      const res = await api.calendar(q.trim());
      setLive(res?.events || []);
    }, 400);
    return () => clearTimeout(t);
  }, [q]);

  const list = live !== null ? live : events;

  // Mini month (static 2026-06)
  const today = 28;
  const startWeekday = 1; // 2026-06-01 is Monday
  const daysInMonth = 30;
  const cells: (number | null)[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  const eventDays = list.map((e) => new Date(e.when_dt).getDate());

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="calendar · /calendar?q="
        title="自动日历 · 从转录中确定性提取"
        icon="fa-calendar-days"
        right={
          <span
            className="chip"
            style={{
              color: "#9DDBC1",
              background: "rgba(63,182,139,0.10)",
              borderColor: "rgba(63,182,139,0.35)",
            }}
          >
            🔒 when_dt 由 temporal 解析
          </span>
        }
      />

      <div className="glass p-4 mb-5 flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[260px] relative">
          <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-text-mute text-[12px]" />
          <input
            className="input pl-9"
            placeholder='自然语言检索："明天" / "下周五" / "Lily"'
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 text-[11px] text-text-mute">
          <span>q 直达后端 /calendar?q=</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 glass p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[14px] font-semibold">2026 年 6 月</div>
            <div className="flex items-center gap-1">
              <button className="w-7 h-7 rounded-md hover:bg-bg-elev-2 text-text-dim">
                <i className="fas fa-chevron-left text-[11px]" />
              </button>
              <button className="w-7 h-7 rounded-md hover:bg-bg-elev-2 text-text-dim">
                <i className="fas fa-chevron-right text-[11px]" />
              </button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1.5 text-center text-[10.5px] text-text-mute mb-2">
            {["日", "一", "二", "三", "四", "五", "六"].map((d) => (
              <div key={d}>{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {cells.map((d, i) => {
              if (!d) return <div key={i} />;
              const isToday = d === today;
              const hasEv = eventDays.includes(d);
              return (
                <div
                  key={i}
                  className={
                    "aspect-square rounded-md flex flex-col items-center justify-center text-[12px] relative " +
                    (isToday
                      ? "bg-indigo text-white font-semibold"
                      : "text-text-dim hover:bg-bg-elev-2 cursor-pointer")
                  }
                >
                  <span>{d}</span>
                  {hasEv && !isToday && (
                    <span className="w-1 h-1 rounded-full bg-gold mt-0.5" />
                  )}
                  {hasEv && isToday && (
                    <span className="w-1 h-1 rounded-full bg-white mt-0.5" />
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-5 p-3 rounded-lg bg-bg-elev-2 border border-border-soft text-[12px] text-text-dim leading-5">
            <i className="fas fa-circle-info text-gold mr-1.5" />
            日期点为确定性解析得到；点击事件可跳源转录，查看是哪一句话被解析。
          </div>
        </div>

        <div className="lg:col-span-3 glass p-5">
          <div className="text-[12px] uppercase tracking-[0.22em] text-text-mute mb-3">
            events · {list.length}
          </div>
          {list.length === 0 ? (
            <Empty icon="fa-calendar-xmark" title="没有匹配的事件" />
          ) : (
            <div className="space-y-3">
              {list.map((e: any) => (
                <div
                  key={e.id}
                  className="p-4 rounded-xl border border-border-soft bg-bg-elev-2 hover:border-[#33415A] transition"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-[14px] font-semibold text-text">
                        {e.title}
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-[12px] text-text-dim flex-wrap">
                        <span>
                          <i className="fas fa-user mr-1" />
                          {e.who}
                        </span>
                        <span>
                          <i className="fas fa-location-dot mr-1" />
                          {e.where}
                        </span>
                      </div>
                    </div>
                    <SourceChip
                      type="segment"
                      id={e.source_segment}
                      label={e.source_segment}
                    />
                  </div>
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-[12px]">
                    <div className="p-2.5 rounded-md bg-bg border border-border-soft">
                      <div className="text-[10.5px] uppercase tracking-widest text-text-mute mb-1">
                        when_raw · 源表达
                      </div>
                      <div className="text-text mono">"{e.when_raw}"</div>
                    </div>
                    <div
                      className="p-2.5 rounded-md border"
                      style={{
                        background: "rgba(63,182,139,0.06)",
                        borderColor: "rgba(63,182,139,0.3)",
                      }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-[10.5px] uppercase tracking-widest text-text-mute">
                          when_dt · 解析
                        </div>
                        <span
                          className="chip"
                          style={{
                            color: "#9DDBC1",
                            background: "rgba(63,182,139,0.10)",
                            borderColor: "rgba(63,182,139,0.35)",
                          }}
                        >
                          🔒 规则
                        </span>
                      </div>
                      <div className="text-green mono">{e.when_dt}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
