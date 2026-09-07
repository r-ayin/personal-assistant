"use client";

import { useState } from "react";
import DestinationPage from "@/components/DestinationPage";
import PortraitSelfPanel from "@/components/panels/PortraitSelfPanel";
import PortraitCirclesPanel from "@/components/panels/PortraitCirclesPanel";
import PortraitPersonPanel from "@/components/panels/PortraitPersonPanel";
import PortraitMetricsPanel from "@/components/panels/PortraitMetricsPanel";
import dynamic from "next/dynamic";

// 科普整版的文案数据约 15K，进首屏 chunk 会超性能合约——异步加载，
// 与图表层、wiki 菌丝图同一合约（ssr:false）。
const PortraitSciencePanel = dynamic(() => import("@/components/panels/PortraitSciencePanel"), {
  ssr: false,
  loading: () => (
    <p className="py-8 text-center font-mono text-[12px] text-[var(--text-weak)]">
      科普内容加载中…
    </p>
  ),
});

/** 首帧从 URL 读 ?person=（客户端运行时读取，静态导出安全） */
function initialPerson(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("person");
}

/**
 * 「画像」目的地：我 / 关系圈 / 单人档案 / 复杂度指标 / 指标科普。
 * 数据全部来自 /portrait/*（只读 memory.db）；空则诚实空态，绝不编造画像。
 * 关系圈点人 → 切到单人档案 tab 并带上 personId。
 */
export default function PortraitPage() {
  const [personId, setPersonId] = useState<string | null>(initialPerson);

  return (
    <DestinationPage
      title="画像"
      titles={{ self: "我", circles: "关系圈", person: "单人档案", metrics: "复杂度指标", science: "指标科普" }}
      panels={({ setTab }) => ({
        self: <PortraitSelfPanel />,
        circles: (
          <PortraitCirclesPanel
            onSelect={(id) => {
              setPersonId(id);
              setTab("person");
            }}
          />
        ),
        person: <PortraitPersonPanel personId={personId} />,
        metrics: <PortraitMetricsPanel />,
        science: <PortraitSciencePanel onGoMetrics={() => setTab("metrics")} />,
      })}
    />
  );
}
