"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, SourceChip, GenerativeBadge, Empty } from "@/components/ui";

const kinds = [
  { k: "book", t: "图书", icon: "fa-book" },
  { k: "movie", t: "影片", icon: "fa-film" },
  { k: "action", t: "行动", icon: "fa-bolt" },
];

export default function RecommendPage() {
  const [kind, setKind] = useState("book");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      const res = await api.recommend(kind, q.trim());
      const recs = (res?.recommendations || []).map((r: any) => ({
        item: r.item,
        reason: r.reason,
        based_on: r.based_on ? [r.based_on] : [],
        from_search: kind !== "action",
      }));
      setItems(recs);
      setLoading(false);
    }, 300);
    return () => clearTimeout(t);
  }, [kind, q]);

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="recommend · /recommend"
        title="推荐引擎"
        icon="fa-sparkles"
        right={
          <>
            <GenerativeBadge />
            <span className="text-[12px] text-text-dim">based_on 必须落地</span>
          </>
        }
      />

      <div className="glass p-4 mb-5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-1.5">
          {kinds.map((it) => (
            <button
              key={it.k}
              onClick={() => setKind(it.k)}
              className={
                "px-3 py-2 rounded-md text-[12.5px] transition flex items-center gap-1.5 " +
                (kind === it.k
                  ? "bg-indigo-soft text-indigo border border-indigo/30"
                  : "text-text-dim border border-transparent hover:border-border")
              }
            >
              <i className={"fas " + it.icon} /> {it.t}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-[360px] min-w-[200px]">
          <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-text-mute text-[12px]" />
          <input
            className="input pl-9"
            placeholder="可选 query（缩窄推荐范围）"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="glass p-8 text-text-dim">加载中…</div>
      ) : items.length === 0 ? (
        <Empty
          icon="fa-ghost"
          title="暂无推荐"
          hint="后端会基于联网搜索 + persona 维度生成；无落地结果时不展示假数据。"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((it, idx) => (
            <div key={idx} className="glass card-hover p-5 flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-gold-soft text-gold flex items-center justify-center">
                  <i
                    className={
                      "fas " +
                      (kind === "book"
                        ? "fa-book-bookmark"
                        : kind === "movie"
                          ? "fa-clapperboard"
                          : "fa-bolt-lightning")
                    }
                  />
                </div>
                {it.from_search && (
                  <span className="chip chip-indigo">
                    <i className="fas fa-globe" style={{ fontSize: 9 }} /> 联网搜索
                  </span>
                )}
              </div>
              <div className="text-[14.5px] font-semibold text-text leading-snug">
                {it.item}
              </div>
              <p className="mt-2 text-[12.5px] text-text-dim leading-5 flex-1">
                {it.reason}
              </p>
              <div className="mt-3 pt-3 border-t border-border-soft">
                <div className="text-[10.5px] uppercase tracking-widest text-text-mute mb-1.5">
                  based_on
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {it.based_on.map((b: string) => {
                    const [type, id] = b.split(":");
                    return (
                      <SourceChip
                        key={b}
                        type={type === "mem" ? "memory" : type}
                        id={id}
                        label={id}
                      />
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
