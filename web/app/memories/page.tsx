"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, MemoryCard, Empty } from "@/components/ui";

export default function MemoriesPage() {
  const [all, setAll] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");

  useEffect(() => {
    (async () => {
      const res = await api.memories();
      setAll(res?.memories || []);
    })();
  }, []);

  const kinds = ["all", "event", "preference", "intention", "emotion"];

  const list = useMemo(() => {
    return all.filter((x) => {
      if (kind !== "all" && x.kind !== kind) return false;
      if (q && !x.content.includes(q)) return false;
      return true;
    });
  }, [all, q, kind]);

  const counts = useMemo(() => {
    return kinds.reduce((acc: Record<string, number>, k) => {
      acc[k] =
        k === "all" ? all.length : all.filter((x) => x.kind === k).length;
      return acc;
    }, {});
  }, [all]);

  const evidenceLanded = all.filter((x) => x.evidence).length;

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="memory · /memories"
        title="记忆库 · 语义可检索"
        icon="fa-brain"
        right={
          <span className="text-[12px] text-text-dim">
            共 {all.length} 条 · evidence 落地 {evidenceLanded}/{all.length}
          </span>
        }
      />

      <div className="glass p-4 mb-5">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-[260px] relative">
            <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-text-mute text-[12px]" />
            <input
              className="input pl-9"
              placeholder="语义检索（如：阅读 / Lily / 喂药）"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-1.5">
            {kinds.map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={
                  "px-3 py-1.5 rounded-md text-[12px] transition " +
                  (kind === k
                    ? "bg-indigo-soft text-indigo border border-indigo/30"
                    : "text-text-dim border border-transparent hover:border-border")
                }
              >
                {k} <span className="opacity-60 mono ml-1">{counts[k]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {list.length === 0 ? (
        <Empty
          icon="fa-magnifying-glass-minus"
          title="没找到匹配的记忆"
          hint="试试改关键词或清空筛选。"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {list.map((mem) => (
            <MemoryCard key={mem.id} mem={mem} />
          ))}
        </div>
      )}
    </div>
  );
}
