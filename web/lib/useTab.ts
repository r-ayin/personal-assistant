"use client";

import { useCallback, useEffect, useState } from "react";
import type { NavDef } from "@/lib/nav";

/**
 * tab 状态 ↔ URL `?tab=<id>` 双向同步。
 *
 * 刻意不用 next/navigation 的 useSearchParams：静态导出（output:"export"）下它
 * 要求 Suspense 边界，否则构建期报 CSR bailout。直接读 window.location 既避开
 * 这个约束，也让 tab 切换用 history.replaceState 完成，不触发路由重载——
 * 这样 AnimatePresence 才能做出连续的横向转场。
 */
export function useTab(nav: NavDef | undefined) {
  const tabs = nav?.tabs ?? [];
  const ids = tabs.map((t) => t.id);
  const fallback = ids[0] ?? "";
  const navPath = nav?.path ?? "";

  const [tab, setTabState] = useState(fallback);
  /** 转场方向：1 = 向右切（后面的 tab），-1 = 向左切 */
  const [dir, setDir] = useState<1 | -1>(1);

  // 挂载后与主导航切换后，从 URL 读初值，避免静态导出的 hydration 不一致
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab");
    if (q && ids.includes(q)) {
      setTabState(q);
    } else if (fallback) {
      setTabState(fallback);
    }
    // ids 每次渲染都是新数组，只在 navPath 变化时重算
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navPath]);

  const setTab = useCallback((id: string) => {
    if (!ids.includes(id) || id === tab) return;
    setDir(ids.indexOf(id) >= ids.indexOf(tab) ? 1 : -1);
    setTabState(id);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", id);
      window.history.replaceState(null, "", url.toString());
    }
    // ids 每次渲染都是新数组，用 join 后的字符串做稳定依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join("|"), tab]);

  return { tabs, tab, dir, setTab };
}
