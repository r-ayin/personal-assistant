"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, Tag } from "@/components/ui";

export default function RemindersPage() {
  const [reminders, setReminders] = useState<any[]>([]);
  const [checking, setChecking] = useState(false);

  const load = async () => {
    const res = await api.reminders();
    setReminders(res?.reminders || []);
  };

  useEffect(() => {
    load();
  }, []);

  const doCheck = async () => {
    setChecking(true);
    await api.remindersCheck();
    await load();
    setChecking(false);
  };

  const pending = reminders.filter((r) => !r.fired);
  const fired = reminders.filter((r) => r.fired);

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="reminders · /reminders"
        title="定时提醒"
        icon="fa-bell"
        right={
          <>
            <span className="text-[12px] text-text-dim">
              {pending.length} 待发 · {fired.length} 已发
            </span>
            <button
              className={"btn btn-primary " + (checking ? "opacity-70" : "")}
              onClick={doCheck}
              disabled={checking}
            >
              <i
                className={"fas " + (checking ? "fa-spinner fa-spin" : "fa-stopwatch")}
              />{" "}
              {checking ? "检查中…" : "立即检查到点"}
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Column
          title="待触发"
          icon="fa-clock"
          tone="indigo"
          items={pending}
          empty="暂无待触发提醒。"
        />
        <Column
          title="已触发"
          icon="fa-circle-check"
          tone="green"
          items={fired}
          empty="还没有触发记录。"
        />
      </div>

      <div className="mt-6 glass p-4 text-[12px] text-text-dim flex items-start gap-2">
        <i className="fas fa-shield-halved text-green mt-0.5" />
        <div>
          所有 <span className="text-text">when_dt</span> 由{" "}
          <span className="mono">temporal.resolve</span>{" "}
          确定性解析得到（🔒），与 LLM 生成内容视觉区分。Android 端命中 fired
          走本地通知通道；Web 仅展示。
        </div>
      </div>
    </div>
  );
}

function Column({
  title,
  icon,
  tone,
  items,
  empty,
}: {
  title: string;
  icon: string;
  tone: "indigo" | "green";
  items: any[];
  empty: string;
}) {
  const toneCls = {
    indigo: "text-indigo",
    green: "text-green",
  }[tone];
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 mb-4">
        <i className={"fas " + icon + " " + toneCls} />
        <div className="text-[14px] font-semibold">{title}</div>
        <span className="ml-1 text-[11px] text-text-mute mono">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="text-[12px] text-text-mute italic py-6 text-center">{empty}</div>
      ) : (
        <div className="space-y-3">
          {items.map((r: any) => (
            <div
              key={r.id}
              className="p-4 rounded-xl border border-border-soft bg-bg-elev-2"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="text-[13.5px] text-text flex-1">{r.what}</div>
                {r.recurring && <Tag color="blue">{r.recurring}</Tag>}
                {r.fired ? (
                  <Tag color="green">已触发</Tag>
                ) : (
                  <Tag color="gold">待发</Tag>
                )}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[11.5px]">
                <div className="p-2 rounded-md bg-bg border border-border-soft">
                  <div className="text-[10px] uppercase tracking-widest text-text-mute">
                    when_raw
                  </div>
                  <div className="text-text-dim mono mt-0.5">
                    "{r.when_raw || "—"}"
                  </div>
                </div>
                <div
                  className="p-2 rounded-md bg-bg border"
                  style={{
                    borderColor: "rgba(63,182,139,0.3)",
                  }}
                >
                  <div className="text-[10px] uppercase tracking-widest text-text-mute">
                    when_dt 🔒
                  </div>
                  <div className="text-green mono mt-0.5">{r.when_dt}</div>
                </div>
              </div>
              {r.source_segment && (
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className="chip chip-indigo hover:brightness-125 cursor-pointer mono"
                    title={"跳源 segment:" + r.source_segment}
                  >
                    <i className="fas fa-waveform-lines" style={{ fontSize: 9 }} />
                    段落:{r.source_segment}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
