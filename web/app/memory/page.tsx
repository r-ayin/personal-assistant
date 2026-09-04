"use client";

import DestinationPage from "@/components/DestinationPage";
import MomentsPanel from "@/components/panels/MomentsPanel";
import KnowledgePanel from "@/components/panels/KnowledgePanel";
import MemorySearchPanel from "@/components/panels/MemorySearchPanel";

/**
 * 「记忆」目的地：时刻 / 检索 / 知识。
 * 检索接 /memory/search（FTS5 bigram + 向量网关 + RRF + GA 终排）；
 * 向量网关不在线时后端自动降级为纯 FTS 并在 sources 里标明。
 */
export default function MemoryPage() {
  return (
    <DestinationPage
      title="记忆"
      titles={{ moments: "时刻", search: "检索", knowledge: "知识" }}
      panels={{
        moments: <MomentsPanel />,
        search: <MemorySearchPanel />,
        knowledge: <KnowledgePanel />,
      }}
    />
  );
}
