"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  SectionHeader,
  TimeChip,
  SourceChip,
  Tag,
  MemoryCard,
  Empty,
} from "@/components/ui";

export default function InboxPage() {
  const [segments, setSegments] = useState<any[]>([]);
  const [speakers, setSpeakers] = useState<any[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [reminders, setReminders] = useState<any[]>([]);

  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [scanning, setScanning] = useState(false);

  const loadAll = async () => {
    const segs = await api.segments("50", "0");
    setSegments(segs?.segments || []);
    const spks = await api.speakers();
    setSpeakers(spks?.speakers || []);
    const mems = await api.memories();
    setMemories(mems?.memories || []);
    const evs = await api.events();
    setEvents(evs?.events || []);
    const rems = await api.reminders();
    setReminders(rems?.reminders || []);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const doIngest = async () => {
    setScanning(true);
    await api.ingest();
    const segs = await api.segments("50", "0");
    setSegments(segs?.segments || []);
    setScanning(false);
  };

  const doUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const buf = await f.arrayBuffer();
    await api.uploadInbox(f.name, buf);
    await doIngest();
    e.target.value = "";
  };

  const filteredSegments = useMemo(() => {
    if (filter === "all") return segments;
    return segments.filter((s) => s.speaker === filter);
  }, [segments, filter]);

  const relatedMems = (segId: string) =>
    memories.filter((x) => x.segment_id === segId);
  const relatedEvents = (segId: string) =>
    events.filter((x) => x.source_segment === segId);
  const relatedReminders = (segId: string) =>
    reminders.filter((x) => x.source_segment === segId);

  const sel = segments.find((s) => s.id === selected);

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="inbox · /segments"
        title="接入转录流"
        icon="fa-inbox"
        right={
          <>
            <input
              type="file"
              accept=".txt,.srt"
              className="hidden"
              onChange={doUpload}
              id="inbox-upload"
            />
            <button
              className="btn btn-ghost"
              onClick={() => document.getElementById("inbox-upload")?.click()}
            >
              <i className="fas fa-upload" /> 上传 .txt / .srt
            </button>
            <button
              className={"btn btn-primary " + (scanning ? "opacity-70" : "")}
              onClick={doIngest}
              disabled={scanning}
            >
              <i className={"fas " + (scanning ? "fa-spinner fa-spin" : "fa-bolt")} />
              {scanning ? "扫描中…" : "立即扫描 inbox"}
            </button>
          </>
        }
      />

      <div className="glass p-4 mb-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-[12px]">
          <span className="text-text-mute mr-1">说话人 ·</span>
          {speakers.map((s: any) => (
            <span
              key={s.name}
              className={"chip " + (s.name === "A" ? "chip-indigo" : "")}
            >
              <i className="fas fa-user-tag" style={{ fontSize: 9 }} /> {s.name} · {s.label}
            </span>
          ))}
          <span className="ml-2 text-text-mute text-[11px]">来自 TextDiarizer（heuristic）</span>
        </div>
        <div className="flex items-center gap-1 text-[12px]">
          {[
            { k: "all", t: "全部" },
            { k: "A", t: "仅我" },
            { k: "B", t: "仅他人" },
          ].map((f) => (
            <button
              key={f.k}
              onClick={() => setFilter(f.k)}
              className={
                "px-3 py-1.5 rounded-md transition " +
                (filter === f.k
                  ? "bg-indigo-soft text-indigo"
                  : "text-text-dim hover:bg-bg-elev-2")
              }
            >
              {f.t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 glass p-5">
          <div className="text-[12px] uppercase tracking-[0.22em] text-text-mute mb-3">
            timeline · 共 {filteredSegments.length} 段
          </div>
          <div className="space-y-2">
            {filteredSegments.map((s: any) => {
              const isSel = s.id === selected;
              const isUser = s.speaker === "A";
              return (
                <button
                  key={s.id}
                  onClick={() => setSelected(s.id)}
                  className={
                    "w-full text-left p-3 rounded-lg border transition flex gap-3 " +
                    (isSel
                      ? "border-indigo bg-indigo-soft"
                      : "border-transparent hover:border-border hover:bg-bg-elev-2")
                  }
                >
                  <span
                    className={
                      "w-7 h-7 shrink-0 rounded-md flex items-center justify-center text-[11px] font-semibold " +
                      (isUser
                        ? "bg-indigo text-white"
                        : "bg-[#2A3142] text-text-dim")
                    }
                  >
                    {s.speaker}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13.5px] leading-6 text-text">{s.text}</p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      <TimeChip
                        created_at={s.created_at}
                        time_kind={s.time_kind}
                        compact
                      />
                      <span className="mono text-[10.5px] text-text-mute">
                        <i className="fas fa-file-lines mr-1" />
                        {s.source_file} · {s.start_sec.toFixed(1)}–
                        {s.end_sec.toFixed(1)}s
                      </span>
                      <span className="mono text-[10.5px] text-text-mute">{s.id}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-2 glass p-5 self-start sticky top-6">
          {!sel ? (
            <Empty
              icon="fa-arrow-left-long"
              title="选中左侧段落查看反查关联"
              hint="点击任意段落可展开它派生的记忆 / 事件 / 提醒。"
            />
          ) : (
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-text-mute mb-2">
                segment · {sel.id}
              </div>
              <p className="text-[14px] leading-6 text-text bg-bg-elev-2 p-3 rounded-md border border-border-soft">
                "{sel.text}"
              </p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <TimeChip
                  created_at={sel.created_at}
                  time_kind={sel.time_kind}
                  compact
                />
                <Tag>language: {sel.language}</Tag>
                <Tag>processed: {sel.processed ? "yes" : "no"}</Tag>
              </div>

              <div className="mt-5 space-y-4">
                <InboxBlock
                  icon="fa-brain"
                  title="派生记忆"
                  items={relatedMems(sel.id)}
                  render={(mem: any) => <MemoryCard mem={mem} key={mem.id} />}
                />
                <InboxBlock
                  icon="fa-calendar"
                  title="派生事件"
                  items={relatedEvents(sel.id)}
                  render={(e: any) => (
                    <div
                      key={e.id}
                      className="p-3 rounded-lg bg-bg-elev-2 border border-border-soft"
                    >
                      <div className="text-[13px] text-text">{e.title}</div>
                      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] text-text-mute mono">
                          原文：{e.when_raw}
                        </span>
                        <span className="chip" style={{ color: "#9DDBC1", background: "rgba(63,182,139,0.10)", borderColor: "rgba(63,182,139,0.35)" }}>
                          🔒 {e.when_dt}
                        </span>
                      </div>
                    </div>
                  )}
                />
                <InboxBlock
                  icon="fa-bell"
                  title="派生提醒"
                  items={relatedReminders(sel.id)}
                  render={(r: any) => (
                    <div
                      key={r.id}
                      className="p-3 rounded-lg bg-bg-elev-2 border border-border-soft"
                    >
                      <div className="text-[13px] text-text">{r.what}</div>
                      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                        <span className="chip" style={{ color: "#9DDBC1", background: "rgba(63,182,139,0.10)", borderColor: "rgba(63,182,139,0.35)" }}>
                          🔒 {r.when_dt}
                        </span>
                        {r.recurring && <Tag color="blue">{r.recurring}</Tag>}
                      </div>
                    </div>
                  )}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InboxBlock({
  icon,
  title,
  items,
  render,
}: {
  icon: string;
  title: string;
  items: any[];
  render: (it: any) => React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2 text-[12px] text-text-dim">
        <i className={"fas " + icon} /> {title} · {items.length}
      </div>
      {items.length === 0 ? (
        <div className="text-[12px] text-text-mute italic">无关联</div>
      ) : (
        <div className="space-y-2">{items.map(render)}</div>
      )}
    </div>
  );
}
