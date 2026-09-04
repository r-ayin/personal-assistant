"use client";

import { useMemo } from "react";
import { api } from "@/lib/api";
import { HonestEmpty, MetricRow, useAsync } from "@/components/portrait-bits";
import { SectionHeader } from "@/components/ui";
import type { PortraitMetricRow } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  self: "我", person: "人物", conversation: "会话",
};

/** 复杂度指标 tab：按 subject_kind 分组；每行 value+CI+n，eligible=0 灰显给理由 */
export default function PortraitMetricsPanel() {
  const { loading, error, data } = useAsync(() => api.portraitMetrics(), []);

  const groups = useMemo(() => {
    const rows = data?.metrics ?? [];
    const g = new Map<string, PortraitMetricRow[]>();
    for (const r of rows) {
      const k = r.subject_kind;
      g.set(k, [...(g.get(k) ?? []), r]);
    }
    return [...g.entries()];
  }, [data]);

  if (loading) return <HonestEmpty title="正在读取指标…" />;
  if (error) return <HonestEmpty title="连不上后端" hint={error} />;
  if (!data?.available) return <HonestEmpty title="指标库尚未建立" hint="跑 memcore.metrics run 后这里会长出数字" />;
  if (!groups.length) {
    return (
      <HonestEmpty
        title="还没有任何指标"
        hint="18 项复杂科学指标都带 n / 置信区间 / 零假设基线；样本不足的会灰显并说明理由，而不是编一个数"
      />
    );
  }

  return (
    <div className="space-y-10">
      {groups.map(([kind, rows]) => (
        <section key={kind}>
          <SectionHeader
            title={KIND_LABEL[kind] ?? kind}
            subtitle={`${rows.length} 项 · eligible ${rows.filter((r) => r.eligible === 1).length}`}
          />
          <div className="glass-card p-6 cv-auto">
            {rows.map((m, i) => <MetricRow key={`${m.subject_id}-${m.name}-${i}`} m={m} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
