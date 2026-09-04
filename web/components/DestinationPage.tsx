"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { navForPath } from "@/lib/nav";
import { useTab } from "@/lib/useTab";
import PageTransition from "@/components/PageTransition";
import TabRail, { TabPanel } from "@/components/TabRail";

/**
 * 主导航目的地的统一外壳：tab 条 + 标题 + 带方向的转场面板。
 *
 * 5 个目的地（今天/对话/画像/记忆/系统）共用这一层，二级内容走 ?tab=<id>。
 * tab 用客户端状态而非嵌套路由，静态导出下才能做连续横向转场而不是整页重载。
 */
export default function DestinationPage({
  title, subtitle, meta, panels, titles,
}: {
  title: string;
  subtitle?: string;
  meta?: ReactNode;
  /** tab id → 面板内容；也可传函数拿到 {tab, setTab} 做面板间联动 */
  panels:
    | Record<string, ReactNode>
    | ((ctx: { tab: string; setTab: (t: string) => void }) => Record<string, ReactNode>);
  /** 可选：每个 tab 各自的标题，覆盖 destination 级标题 */
  titles?: Record<string, string>;
}) {
  const pathname = usePathname() || "";
  const nav = navForPath(pathname);
  const { tabs, tab, dir, setTab } = useTab(nav);
  const resolved = typeof panels === "function" ? panels({ tab, setTab }) : panels;
  const active = tab && resolved[tab] !== undefined ? tab : (tabs[0]?.id ?? "");

  return (
    <>
      <TabRail tabs={tabs} active={active} onChange={setTab} />
      <PageTransition
        title={(titles?.[active]) || title}
        subtitle={subtitle}
        meta={meta}
      >
        <TabPanel id={active} dir={dir}>
          {resolved[active] ?? null}
        </TabPanel>
      </PageTransition>
    </>
  );
}
