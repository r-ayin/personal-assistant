"use client";

import DestinationPage from "@/components/DestinationPage";
import IngestPanel from "@/components/panels/IngestPanel";
import AssistantPersonaPanel from "@/components/panels/AssistantPersonaPanel";
import VerifyPanel from "@/components/panels/VerifyPanel";
import SettingsPanel from "@/components/panels/SettingsPanel";

/** 「系统」目的地：摄入 / 助手人格 / 校验 / 设置，四个面板全部由旧页面抽取而来。 */
export default function SystemPage() {
  return (
    <DestinationPage
      title="系统"
      panels={{
        ingest: <IngestPanel />,
        persona: <AssistantPersonaPanel />,
        verify: <VerifyPanel />,
        settings: <SettingsPanel />,
      }}
    />
  );
}
