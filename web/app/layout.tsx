import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "PA · 今天",
  description: "Personal Assistant 对话工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="pa-shell">
          <Sidebar />
          <main className="pa-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
