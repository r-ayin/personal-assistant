"use client";

import { useEffect, useState } from "react";
import { legacyTarget } from "@/lib/nav";

/**
 * 旧路由 → 新 IA 的客户端重定向。
 *
 * 静态导出（output:"export"）不支持 next.config 的 redirects()，只能在客户端跳。
 * basePath 是 /web，必须自己拼回去，否则会跳到站点外。
 */
export default function LegacyRedirect({ from }: { from: string }) {
  const [target, setTarget] = useState<string | null>(null);

  useEffect(() => {
    const to = legacyTarget(from);
    if (!to) return;
    // 从当前 URL 取 basePath：/web/xxx → /web
    const base = window.location.pathname.startsWith("/web") ? "/web" : "";
    const next = base + to;
    setTarget(next);
    window.location.replace(next);
  }, [from]);

  return (
    <div className="pa-page">
      <p className="font-serif text-[14px] text-[var(--text-dim)]">
        {target ? `正在前往 ${target} …` : "正在跳转…"}
      </p>
    </div>
  );
}
