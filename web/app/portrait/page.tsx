"use client";

import { useState } from "react";
import DestinationPage from "@/components/DestinationPage";
import PortraitSelfPanel from "@/components/panels/PortraitSelfPanel";
import PortraitCirclesPanel from "@/components/panels/PortraitCirclesPanel";
import PortraitPersonPanel from "@/components/panels/PortraitPersonPanel";
import PortraitMetricsPanel from "@/components/panels/PortraitMetricsPanel";

/** 首帧从 URL 读 ?person=（客户端运行时读取，静态导出安全） */
function initialPerson(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("person");
}

/**
 * 「画像」目的地：我 / 关系圈 / 单人档案 / 复杂度指标。
 * 数据全部来自 /portrait/*（只读 memory.db）；空则诚实空态，绝不编造画像。
 * 关系圈点人 → 切到单人档案 tab 并带上 personId。
 */
export default function PortraitPage() {
  const [personId, setPersonId] = useState<string | null>(initialPerson);

  return (
    <DestinationPage
      title="画像"
      titles={{ self: "我", circles: "关系圈", person: "单人档案", metrics: "复杂度指标" }}
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
      })}
    />
  );
}
