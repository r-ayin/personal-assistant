"use client";

import { useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/EmptyState";
import CalendarTimeline, { type DayGroup } from "@/components/calendar-timeline";
import { LoadingDots, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import type { Event } from "@/lib/types";

/** 按日（when_dt 前 10 位）分组，日序与日内时序均升序 */
function groupByDay(events: Event[]): DayGroup[] {
  const map = new Map<string, Event[]>();
  for (const ev of events) {
    const day = (ev.when_dt || "").slice(0, 10) || "未定时日";
    const list = map.get(day) || [];
    list.push(ev);
    map.set(day, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, evs]) => ({
      day,
      events: [...evs].sort((a, b) => (a.when_dt || "").localeCompare(b.when_dt || "")),
    }));
}

/** 「今天 · 日程」面板：原 /calendar/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function SchedulePanel() {
  const [allEvents, setAllEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<{ q: string; events: Event[] } | null>(null);
  const [searchError, setSearchError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .events()
      .then((res) => {
        if (cancelled) return;
        setAllEvents(res.events || []);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function runSearch() {
    const q = query.trim();
    if (!q) {
      setSearchResult(null);
      setSearchError(false);
      return;
    }
    setSearching(true);
    setSearchError(false);
    const res = await api.calendar(q);
    setSearching(false);
    if (res === null) {
      setSearchResult({ q, events: [] });
      setSearchError(true);
      return;
    }
    setSearchResult({ q: res.query || q, events: res.events || [] });
  }

  const displayed = searchResult ? searchResult.events : allEvents;
  const groups = useMemo(() => groupByDay(displayed), [displayed]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingDots label="正在召回时光……" />
      </div>
    );
  }

  return (
    <div>
      {/* ── 搜索：回车启程 ── */}
      <div className="mb-10">
        <input
          className="input-glow"
          style={{ maxWidth: 380 }}
          placeholder="搜索时光，回车启程……"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") runSearch();
          }}
          aria-label="搜索日程"
        />
      </div>

      {/* ── 搜索结果提示 ── */}
      {searchResult && !searching && (
        <div className="flex items-center gap-4 mb-8 flex-wrap">
          <WhisperLine delay={0}>
            {searchError
              ? "炉火熄了——连不上后端"
              : `关于「${searchResult.q}」的 ${searchResult.events.length} 段时光`}
          </WhisperLine>
          <button
            className="btn-ghost"
            style={{ padding: "6px 14px", fontSize: 13 }}
            onClick={() => {
              setSearchResult(null);
              setSearchError(false);
              setQuery("");
            }}
          >
            查看全部时光
          </button>
        </div>
      )}

      {searching ? (
        <LoadingDots label="正在纸下菌丝间寻找……" />
      ) : groups.length === 0 ? (
        <EmptyState
          message={
            loadError
              ? "炉火熄了——连不上后端"
              : searchResult
                ? `关于「${searchResult.q}」的时光暂未寻见`
                : "日历上还什么都没有，时光尚未落笔"
          }
        />
      ) : (
        <CalendarTimeline groups={groups} />
      )}
    </div>
  );
}
