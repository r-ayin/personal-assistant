"use client";

import { useCallback, useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import ReminderCard, { parseDt } from "@/components/reminders-card";
import { LoadingDots, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import type { Reminder } from "@/lib/types";

/** POST /reminders/check 的响应形状：{ fired: number, items: [...] } */
interface CheckResult {
  fired?: number;
}

/** 「今天 · 提醒」面板：原 /reminders/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function RemindersPanel() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkMsg, setCheckMsg] = useState<string | null>(null);
  // now 在挂载后才取值，避免静态预渲染与水合之间的时间差
  const [now, setNow] = useState<number | null>(null);

  const load = useCallback(async () => {
    const res = await api.reminders().catch(() => null);
    if (res === null) setLoadError(true);
    setReminders(res?.reminders || []);
    setLoading(false);
  }, []);

  useEffect(() => {
    setNow(Date.now());
    load();
    // 余烬环每 30s 轻轻呼吸一次
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, [load]);

  async function checkNow() {
    setChecking(true);
    setCheckMsg(null);
    const res = (await api.remindersCheck()) as CheckResult | null;
    setChecking(false);
    if (res === null) {
      setCheckMsg("炉火熄了——检查没有送达");
      return;
    }
    const fired = typeof res.fired === "number" ? res.fired : 0;
    setCheckMsg(fired > 0 ? `${fired} 条提醒刚刚到期` : "此刻没有提醒到期，炉火安稳");
    // 检查可能改写了 fired 状态，重新拉取让环与标签同步
    const fresh = await api.reminders().catch(() => null);
    if (fresh) setReminders(fresh.reminders || []);
  }

  const sorted = [...reminders].sort((a, b) => {
    const ta = parseDt(a.when_dt);
    const tb = parseDt(b.when_dt);
    if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
    if (Number.isNaN(ta)) return 1;
    if (Number.isNaN(tb)) return -1;
    return ta - tb;
  });

  if (loading || now === null) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingDots label="正在点亮余烬……" />
      </div>
    );
  }

  return (
    <div>
      {/* ── 顶部：一句低语 + 检查到期 ── */}
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <p className="serif text-sm" style={{ color: "var(--text-weak)" }}>
          余烬在环上燃烧，越近越暖。
        </p>
        <button className="btn-ghost" onClick={checkNow} disabled={checking}>
          {checking ? "正在检查……" : "检查到期"}
        </button>
      </div>
      {checkMsg && (
        <div className="mb-8">
          <WhisperLine key={checkMsg} delay={0}>
            {checkMsg}
          </WhisperLine>
        </div>
      )}

      {sorted.length === 0 ? (
        <EmptyState message={loadError ? "炉火熄了——连不上后端" : "没有待办在燃烧，一切安好"} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">
          {sorted.map((r, i) => (
            <ReminderCard key={r.id} reminder={r} now={now} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
