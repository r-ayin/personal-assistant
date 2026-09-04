import type { Metadata } from "next";
import "./globals.css";
import { MotionConfig } from "framer-motion";
import Sidebar from "@/components/Sidebar";
import AmbientField from "@/components/AmbientField";
import StatusStrip from "@/components/StatusStrip";

export const metadata: Metadata = {
  title: "PA · 生命记忆",
  description: "个人助手 — 记忆是一个活着的有机体",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <MotionConfig reducedMotion="user">
          <AmbientField />
          <div className="pa-shell">
            <Sidebar />
            <main className="pa-main">{children}</main>
          </div>
          <StatusStrip />
        </MotionConfig>
      </body>
    </html>
  );
}
