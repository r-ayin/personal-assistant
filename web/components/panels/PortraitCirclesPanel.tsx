"use client";

import { api } from "@/lib/api";
import { HonestEmpty, MetricRow, useAsync } from "@/components/portrait-bits";
import { SectionHeader } from "@/components/ui";

/** 关系圈 tab：按消息量排序的人物 + Dunbar 分层指标。点人切到单人档案。 */
export default function PortraitCirclesPanel({
  onSelect,
}: {
  onSelect: (personId: string) => void;
}) {
  const { loading, error, data } = useAsync(() => api.portraitCircles("80"), []);

  if (loading) return <HonestEmpty title="正在清点你的关系圈…" />;
  if (error) return <HonestEmpty title="连不上后端" hint={error} />;
  if (!data?.available) return <HonestEmpty title="身份归并尚未建立" hint="跑 memcore.identity build 后这里会长出人物" />;

  const people = data.people ?? [];
  const layers = data.layers ?? [];

  return (
    <div className="space-y-10">
      <section>
        <SectionHeader title="人物（按消息量）" subtitle="点击看单人档案；role 来自 identity.json 与归并" />
        {people.length === 0 ? (
          <HonestEmpty title="还没有可展示的人物" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 cv-auto">
            {people.map((p) => (
              <button
                key={p.person_id}
                type="button"
                onClick={() => onSelect(p.person_id)}
                className="glass-card p-5 text-left cursor-pointer"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="serif text-[15px] font-semibold text-[var(--ink-900)] truncate">
                    {p.display_name || p.person_id}
                  </span>
                  {p.role && (
                    <span className="shrink-0 rounded-full bg-[var(--cin-08)] px-2 py-[2px] text-[11px] text-[var(--cinnabar)]">
                      {p.role}
                    </span>
                  )}
                </div>
                <p className="mt-2 font-mono text-[11px] text-[var(--text-weak)]">
                  {p.msgs} 条 · 你 {p.user_msgs} · {p.convs} 会话
                </p>
                <p className="mt-1 font-mono text-[11px] text-[var(--text-weak)]">
                  {(p.first_ts ?? "").slice(0, 10)} ~ {(p.last_ts ?? "").slice(0, 10)}
                </p>
              </button>
            ))}
          </div>
        )}
      </section>

      {!!layers.length && (
        <section>
          <SectionHeader title="社交签名 / 邓巴分层" subtitle="份额分布断点；样本不足的行灰显并给理由" />
          <div className="glass-card p-6 cv-auto">
            {layers.map((m, i) => <MetricRow key={`${m.name}-${i}`} m={m} />)}
          </div>
        </section>
      )}
    </div>
  );
}
