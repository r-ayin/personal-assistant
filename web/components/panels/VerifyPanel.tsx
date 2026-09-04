"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";
import { LoadingDots, MonoCount, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import { VERIFY_LABELS } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { VerifyReport } from "@/lib/types";

const KEPT_KEYS = ["events_kept", "reminders_kept", "memories_kept"] as const;
const DELETED_KEYS = ["events_deleted", "reminders_deleted", "memories_deleted"] as const;

/** 一列分拣玻璃卡：保留（moss）或删除（bloom），数字从上方飘落定位 */
function SortColumn({
  title,
  tone,
  keys,
  report,
  runId,
  baseDelay,
}: {
  title: string;
  tone: "moss" | "bloom";
  keys: readonly (keyof VerifyReport)[];
  report: VerifyReport;
  runId: number;
  baseDelay: number;
}) {
  const solid = tone === "moss" ? "var(--mineral)" : "var(--cinnabar)";
  const deep = tone === "moss" ? "var(--mineral-deep)" : "var(--cinnabar-deep)";
  const soft = tone === "moss" ? "var(--min-10)" : "var(--cin-10)";
  return (
    <Reveal
      as="section"
      className="glass-card p-6"
      transition={{ duration: 0.8, ease: EASE.out, delay: baseDelay }}
    >
      <div className="flex items-center gap-3 mb-2">
        <span
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: solid, boxShadow: `0 0 10px ${soft}` }}
        />
        <h2 className="text-lg font-semibold" style={{ fontFamily: "var(--font-serif)", color: deep }}>
          {title}
        </h2>
      </div>
      <div>
        {keys.map((k, i) => (
          <div
            key={k}
            className="flex items-end justify-between py-4"
            style={{ borderTop: i === 0 ? "none" : "1px solid var(--edge)" }}
          >
            <span className="text-sm" style={{ color: "var(--text-dim)" }}>
              {VERIFY_LABELS[k] || k}
            </span>
            {/* 分拣粒子：数字从上方飘落定位，交错 80ms；runId 变化时重新入场 */}
            <motion.span
              key={`${runId}-${k}`}
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: baseDelay + 0.15 + i * 0.08, duration: 0.8, ease: EASE.out }}
            >
              <MonoCount value={report[k]} size={30} color={deep} />
            </motion.span>
          </div>
        ))}
      </div>
    </Reveal>
  );
}

/** 「系统 · 校验」面板：原 /verify/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function VerifyPanel() {
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [runId, setRunId] = useState(0);

  const run = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await api.verify();
      setReport(res);
      setRunId((n) => n + 1);
    } catch {
      setReport(null);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <div className="space-y-12">
      <p className="text-xs" style={{ color: "var(--text-weak)" }}>
        反幻觉复查——确定性脚本清点每一段记忆的去留
      </p>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <LoadingDots label="正在分拣记忆的去留……" />
        </div>
      ) : error || !report ? (
        <div>
          <EmptyState message="炉火熄了——连不上后端，校验没有完成" />
          <div className="flex justify-center">
            <button type="button" className="btn-ghost" onClick={run}>
              再试一次
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <SortColumn title="保留" tone="moss" keys={KEPT_KEYS} report={report} runId={runId} baseDelay={0.1} />
            <SortColumn title="删除" tone="bloom" keys={DELETED_KEYS} report={report} runId={runId} baseDelay={0.2} />
          </div>
          <div className="flex flex-col items-center gap-6 pt-4">
            <WhisperLine delay={0.7}>校验通过的数字，是记忆没有说谎的证明</WhisperLine>
            <button type="button" className="btn-ghost" onClick={run}>
              重新校验
            </button>
          </div>
        </>
      )}
    </div>
  );
}
