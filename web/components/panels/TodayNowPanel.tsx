"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";
import RingCore from "@/components/RingCore";
import ScrollReveal from "@/components/ScrollReveal";
import { LoadingDots, MonoCount, SeedCard, Tag, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import { momentTagLabel, pick, RECURRING_LABELS, speakerLabel } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { Event, Moment, Reminder } from "@/lib/types";

/** "2026-09-01 21:30" / "2026-09-01T21:30" → "09-01 21:30"（等宽展示） */
function fmtTime(s?: string): string {
  return (s || "").slice(0, 16).replace("T", " ").replace(/^(\d{4})-(\d{2})-(\d{2})/, "$2-$3");
}

/** 本地日期 "YYYY-MM-DD" */
function localDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

/** 按年内日序在未归还时刻中稳定轮换，每日一条 */
function pickWhisper(moments: Moment[]): Moment | null {
  // 优先未归还时刻；全部已归还时从全量轮换——每日一句低语不因归还而熄灭
  const unreturned = moments.filter((m) => !m.recalled);
  const pool = unreturned.length > 0 ? unreturned : moments;
  if (pool.length === 0) return null;
  const now = new Date();
  const dayOfYear = Math.floor(
    (now.getTime() - new Date(now.getFullYear(), 0, 0).getTime()) / 86400000,
  );
  return pool[dayOfYear % pool.length];
}

/** 「今天 · 此刻」面板：年轮核计数 + 今日低语 + 日程/提醒双栏。外壳由 DestinationPage 提供。 */
export default function TodayNowPanel() {
  const [events, setEvents] = useState<Event[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [memoriesCount, setMemoriesCount] = useState<number | null>(null);
  const [memoryYears, setMemoryYears] = useState(1);
  const [whisper, setWhisper] = useState<Moment | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [statusRes, eventsRes, remindersRes, momentsRes] = await Promise.all([
        api.status().catch(() => null),
        api.events().catch(() => null),
        api.reminders().catch(() => null),
        api.moments(),
      ]);
      // 心灯计数：/status 不可用时回退 /health
      let count = statusRes?.memories ?? null;
      if (count === null) {
        const health = await api.health().catch(() => null);
        count = health?.memories ?? null;
      }
      if (cancelled) return;
      if (eventsRes === null || remindersRes === null) setLoadError(true);
      const allMoments = momentsRes?.moments || [];
      const allEvents = eventsRes?.events || [];
      // 记忆年数 = 最早的时刻/日程距今的年跨度（数据驱动，不编造）；无数据 = 第 1 年
      const stamps: number[] = [];
      for (const raw of [
        ...allMoments.map((m) => m.timestamp || m.created_at),
        ...allEvents.map((e) => e.when_dt),
      ]) {
        const t = Date.parse((raw || "").trim().replace(" ", "T"));
        if (!Number.isNaN(t)) stamps.push(t);
      }
      const oldest = stamps.length > 0 ? Math.min(...stamps) : null;
      const years =
        oldest === null
          ? 1
          : Math.max(1, Math.ceil((Date.now() - oldest) / (365.25 * 86400000)));
      setMemoryYears(Math.min(years, 8));
      setMemoriesCount(count);
      setEvents(allEvents);
      setReminders(remindersRes?.reminders || []);
      setWhisper(momentsRes ? pickWhisper(allMoments) : null);
      setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingDots label="炉火正暖，记忆在醒来……" />
      </div>
    );
  }

  // 与日程同题的提醒不重复出现（保留旧有的数据归并逻辑）
  const visibleReminders = reminders.filter((r) => !events.some((e) => e.title === r.what));
  const sortedEvents = [...events].sort((a, b) => (a.when_dt || "").localeCompare(b.when_dt || ""));
  const sortedReminders = [...visibleReminders].sort((a, b) => (a.when_dt || "").localeCompare(b.when_dt || ""));
  const today = new Date();
  const dateLine = `${localDay(today)} · 星期${WEEKDAYS[today.getDay()]}`;

  return (
    <div>
      {/* ── 年轮核：环数=记忆年数自生长，计数逐位弹入，滚动视差 ── */}
      <div className="flex flex-col items-center gap-5 pt-10 pb-16">
        <ScrollReveal y={24} parallax={22}>
          <RingCore
            years={memoryYears}
            count={memoriesCount}
            countLabel={`第 ${memoryYears} 圈年轮，${memoriesCount === null ? "—" : memoriesCount} 段记忆`}
          />
        </ScrollReveal>
        <WhisperLine delay={0.5}>段记忆，正长成第 {memoryYears} 圈年轮</WhisperLine>
        <Reveal
          as="p"
          delay={0.8}
          style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-weak)" }}
        >
          {dateLine}
        </Reveal>
      </div>

      {/* ── 今日低语：一条尚未归还的时刻 ── */}
      {whisper && (
        <ScrollReveal as="section" className="mb-16" y={36}>
          <div className="mb-5">
            <h2 className="serif text-xl font-semibold">今日低语</h2>
            <p className="text-xs mt-1" style={{ color: "var(--text-weak)" }}>
              一段时刻，仍在纸下轻轻呼吸
            </p>
          </div>
          <SeedCard
            quote={whisper.verbatim_quote}
            narrative={whisper.narrative}
            delay={0.2}
            meta={
              <>
                {(whisper.tags || []).map((t) => (
                  <Tag key={t} color="cinnabar">
                    {momentTagLabel(t)}
                  </Tag>
                ))}
                {whisper.counterpart && <span>对 {whisper.counterpart}</span>}
                {whisper.timestamp && <span>{fmtTime(whisper.timestamp)}</span>}
              </>
            }
          />
        </ScrollReveal>
      )}

      {/* ── 日程（靛青）与提醒（赭石）双栏 ── */}
      <ScrollReveal className="grid grid-cols-1 md:grid-cols-2 gap-8 cv-auto" y={40}>
        <Reveal as="section" className="glass-card p-6" delay={0.25}>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-lg font-semibold serif" style={{ color: "var(--indigo)" }}>
              日程
            </h2>
            <MonoCount value={sortedEvents.length} size={13} color="var(--text-weak)" />
          </div>
          {sortedEvents.length === 0 ? (
            <EmptyState message={loadError ? "炉火熄了——连不上后端" : "今天还没有日程，炉火正温"} />
          ) : (
            <div className="space-y-3">
              {sortedEvents.slice(0, 8).map((ev, i) => (
                <motion.div
                  key={ev.id}
                  className="p-3 rounded-xl"
                  style={{
                    border: "1px solid var(--ind-10)",
                    background: "var(--ind-04)",
                  }}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.35 + i * 0.06, duration: 0.7, ease: EASE.out }}
                >
                  <div className="text-sm font-medium">{ev.title}</div>
                  <div
                    className="text-xs mt-1"
                    style={{ color: "var(--indigo-deep)", fontFamily: "var(--font-mono)" }}
                  >
                    {fmtTime(ev.when_dt)}
                  </div>
                  {(ev.who || ev.where) && (
                    <div className="text-xs mt-1" style={{ color: "var(--text-weak)" }}>
                      {[speakerLabel(ev.who), ev.where].filter(Boolean).join(" · ")}
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </Reveal>

        <Reveal as="section" className="glass-card p-6" delay={0.35}>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-lg font-semibold serif" style={{ color: "var(--ochre)" }}>
              提醒
            </h2>
            <MonoCount value={sortedReminders.length} size={13} color="var(--text-weak)" />
          </div>
          {sortedReminders.length === 0 ? (
            <EmptyState message={loadError ? "炉火熄了——连不上后端" : "暂无提醒，一切安好"} />
          ) : (
            <div className="space-y-3">
              {sortedReminders.slice(0, 8).map((r, i) => (
                <motion.div
                  key={r.id}
                  className="p-3 rounded-xl"
                  style={{
                    border: "1px solid var(--och-10)",
                    background: "var(--och-08)",
                  }}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.45 + i * 0.06, duration: 0.7, ease: EASE.out }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium min-w-0 truncate">{r.what}</div>
                    {r.recurring && (
                      <Tag color="ochre">{pick(RECURRING_LABELS, r.recurring)}</Tag>
                    )}
                  </div>
                  <div
                    className="text-xs mt-1"
                    style={{ color: "var(--ochre-deep)", fontFamily: "var(--font-mono)" }}
                  >
                    {fmtTime(r.when_dt)}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </Reveal>
      </ScrollReveal>
    </div>
  );
}
