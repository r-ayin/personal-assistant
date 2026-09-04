"use client";

import PageTransition from "@/components/PageTransition";
import ChatPanel from "@/components/panels/ChatPanel";

/** /chat/：对话没有二级 tab，直接用 PageTransition 外壳，不套 DestinationPage。 */
export default function ChatPage() {
  return (
    <PageTransition title="对话">
      <ChatPanel />
    </PageTransition>
  );
}
