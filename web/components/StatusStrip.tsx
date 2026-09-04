"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { EASE } from "@/lib/motion";
import type { StatusPayload } from "@/lib/types";

/** 底部一线墨痕呼吸条；悬浮浮现全局计数（每 60s 静默轮询） */
export default function StatusStrip() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [hover, setHover] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => api.status().then((s) => { if (alive) setStatus(s); }).catch(() => {});
    load();
    const timer = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  return (
    <div
      className="status-hit"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      aria-hidden="true"
    >
      <div className="status-bar" />
      {status && hover && (
        <motion.div
          initial={{ opacity: 0, y: 6, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.4, ease: EASE.out }}
          style={{
            position: "absolute", bottom: 16, right: 24,
            display: "flex", gap: 14, padding: "6px 14px",
            borderRadius: 999, border: "1px solid var(--edge)",
            background: "var(--porcelain-2)", boxShadow: "var(--elev-pop)",
            fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-weak)",
            pointerEvents: "none",
          }}
        >
          <span>记忆 {status.memories}</span>
          <span>日程 {status.events}</span>
          <span>提醒 {status.reminders}</span>
        </motion.div>
      )}
    </div>
  );
}
