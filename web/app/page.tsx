"use client";

import TodayDestination from "@/components/destinations/TodayDestination";

/** 根路由即「今天」，与 /today/ 渲染同一组件，不做重定向。 */
export default function RootPage() {
  return <TodayDestination />;
}
