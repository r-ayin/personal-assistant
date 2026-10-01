"use client";

import { useMemo } from "react";
import { api } from "@/lib/api";
import { HonestEmpty, MetricRow, useAsync } from "@/components/portrait-bits";
import { Rich, SectionHeader } from "@/components/ui";
import { METRICS_INTRO } from "@/lib/labels-zh";
import type { PortraitMetricRow } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  self: "我", person: "人物", conversation: "会话",
};

/** 复杂度指标 tab：按 subject_kind 分组；每行 value+CI+n，eligible=0 灰显给理由 */
export default function PortraitMetricsPanel() {
  const { loading, error, data } = useAsync(() => api.portraitMetrics(), []);

  // 默认只展示「我」：其他人物/会话的指标从 关系圈 → 点人 → 单人档案 看，
  // 不在这一页平铺（551+ 行的全量列表把「我的数」淹没了）。
  const groups = useMemo(() => {
    const rows = (data?.metrics ?? []).filter((r) => r.subject_kind === "self");
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
        hint="19 项复杂科学指标都带样本量 / 置信区间 / 零假设基线；样本不足的会灰显并说明理由，而不是编一个数"
      />
    );
  }

  return (
    <div className="space-y-10">
      <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-[var(--text-dim)]">
        <Rich text={METRICS_INTRO} />
      </p>
      <p className="max-w-[70ch] text-[12px] leading-relaxed text-[var(--text-weak)]">
        这一页默认只显示你自己的指标。想看某个人的：关系圈 → 点 TA → 单人档案里带 TA 的全部指标。
      </p>
      {groups.map(([kind, rows]) => (
        <section key={kind}>
          <SectionHeader
            title={KIND_LABEL[kind] ?? kind}
            subtitle={`共 ${rows.length} 项 · 可出数 ${rows.filter((r) => r.eligible === 1).length} 项`}
          />
          <div className="glass-card p-6 cv-auto">
            {rows.map((m, i) => <MetricRow key={`${m.subject_id}-${m.name}-${i}`} m={m} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
