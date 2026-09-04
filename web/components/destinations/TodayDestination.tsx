"use client";

import DestinationPage from "@/components/DestinationPage";
import TodayNowPanel from "@/components/panels/TodayNowPanel";
import SchedulePanel from "@/components/panels/SchedulePanel";
import RemindersPanel from "@/components/panels/RemindersPanel";
import RecommendPanel from "@/components/panels/RecommendPanel";

/**
 * 「今天」目的地：4 个 tab 依次是此刻 / 日程 / 提醒 / 推荐。
 *
 * 根路由 app/page.tsx 与 app/today/page.tsx 渲染同一个组件——"/" 就是今天，
 * 不做重定向（见 lib/nav.ts 的 isActive/navForPath 对 "/today/" 的特判）。
 */
export default function TodayDestination() {
  return (
    <DestinationPage
      title="今天"
      titles={{ now: "今天", schedule: "日程", reminders: "提醒", recommend: "推荐" }}
      panels={{
        now: <TodayNowPanel />,
        schedule: <SchedulePanel />,
        reminders: <RemindersPanel />,
        recommend: <RecommendPanel />,
      }}
    />
  );
}
