"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, TimeChip, SourceChip, Tag, Empty } from "@/components/ui";

export default function WikiPage() {
  const [pages, setPages] = useState<any[]>([]);
  const [tag, setTag] = useState("all");
  const [q, setQ] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);

  useEffect(() => {
    (async () => {
      const res = await api.wiki();
      const list = res?.pages || [];
      setPages(list);
      setActiveId(list[0]?.id || null);
    })();
  }, []);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    pages.forEach((p) =>
      p.tags.split(",").forEach((t: string) => s.add(t.trim()))
    );
    return ["all", ...Array.from(s)];
  }, [pages]);

  const filtered = pages.filter((p) => {
    if (tag !== "all" && !p.tags.split(",").map((x: string) => x.trim()).includes(tag))
      return false;
    if (q && !(p.title.includes(q) || p.body.includes(q))) return false;
    return true;
  });

  const active = pages.find((p) => p.id === activeId) || filtered[0];

  const doBuild = async () => {
    setBuilding(true);
    await api.wikiBuild();
    const res = await api.wiki();
    const list = res?.pages || [];
    setPages(list);
    if (list.length && !list.find((p: any) => p.id === activeId)) {
      setActiveId(list[0].id);
    }
    setBuilding(false);
  };

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="wiki · /wiki"
        title="个人 wiki · 增量构建"
        icon="fa-book"
        right={
          <>
            <span className="text-[12px] text-text-dim">{pages.length} 篇</span>
            <button
              className={"btn btn-primary " + (building ? "opacity-70" : "")}
              onClick={doBuild}
              disabled={building}
            >
              <i className={"fas " + (building ? "fa-spinner fa-spin" : "fa-hammer")} />{" "}
              {building ? "构建中…" : "增量构建"}
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <div className="glass p-4">
            <div className="text-[11px] uppercase tracking-widest text-text-mute mb-2">
              标签云
            </div>
            <div className="flex flex-wrap gap-1.5">
              {allTags.map((t) => (
                <button
                  key={t}
                  onClick={() => setTag(t)}
                  className={
                    "px-2.5 py-1 rounded-md text-[11.5px] transition " +
                    (tag === t
                      ? "bg-indigo-soft text-indigo border border-indigo/30"
                      : "bg-bg-elev-2 text-text-dim border border-transparent hover:text-text")
                  }
                >
                  #{t}
                </button>
              ))}
            </div>
          </div>

          <div className="glass p-4">
            <div className="relative mb-3">
              <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-text-mute text-[11px]" />
              <input
                className="input pl-9 text-[12px]"
                placeholder="搜索 wiki…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              {filtered.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setActiveId(p.id)}
                  className={
                    "w-full text-left px-3 py-2 rounded-md text-[12.5px] transition " +
                    (active && active.id === p.id
                      ? "bg-indigo-soft text-indigo"
                      : "text-text-dim hover:bg-bg-elev-2 hover:text-text")
                  }
                >
                  <div className="truncate">{p.title}</div>
                  <div className="mono text-[10px] text-text-mute mt-0.5">
                    {p.created_at.slice(0, 10)}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-3">
          {active ? (
            <div className="glass p-7">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-text-mute mb-2">
                    {active.id}
                  </div>
                  <h2 className="text-[22px] font-semibold tracking-tight">
                    {active.title}
                  </h2>
                </div>
                <TimeChip created_at={active.created_at} time_kind="received" compact />
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {active.tags.split(",").map((t: string) => (
                  <Tag key={t} color="blue">
                    #{t.trim()}
                  </Tag>
                ))}
              </div>

              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="md:col-span-2">
                  <p className="text-[14px] leading-7 text-text whitespace-pre-wrap">
                    {active.body}
                  </p>
                </div>
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-bg-elev-2 border border-border-soft">
                    <div className="text-[10.5px] uppercase tracking-widest text-text-mute mb-2">
                      落地源记忆 ·{" "}
                      {active.source_ids.split(",").filter(Boolean).length}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {active.source_ids
                        .split(",")
                        .filter(Boolean)
                        .map((id: string) => (
                          <SourceChip
                            key={id}
                            type="memory"
                            id={id.trim()}
                            label={id.trim()}
                          />
                        ))}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-bg-elev-2 border border-border-soft">
                    <div className="text-[10.5px] uppercase tracking-widest text-text-mute mb-2">
                      页内互链
                    </div>
                    {active.link_ids ? (
                      <div className="flex flex-wrap gap-1.5">
                        {active.link_ids
                          .split(",")
                          .filter(Boolean)
                          .map((id: string) => {
                            const target = pages.find((p) => p.id === id.trim());
                            return (
                              <button
                                key={id}
                                onClick={() => setActiveId(id.trim())}
                                className="chip chip-green hover:brightness-125"
                              >
                                <i className="fas fa-link" style={{ fontSize: 9 }} />{" "}
                                {target ? target.title : id}
                              </button>
                            );
                          })}
                      </div>
                    ) : (
                      <div className="text-[11px] text-text-mute italic">无互链</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <Empty icon="fa-book-open" title="没有匹配的 wiki 页" />
          )}
        </div>
      </div>
    </div>
  );
}
