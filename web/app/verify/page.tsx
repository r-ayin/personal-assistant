"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionHeader, VerifyBadge } from "@/components/ui";

function mapVerify(v: any) {
  if (!v) {
    return {
      status: "passed",
      passed: 0,
      warned: 0,
      failed: 0,
      total: 0,
      items: [],
    };
  }
  const kept =
    (v.events_kept || 0) + (v.reminders_kept || 0) + (v.memories_kept || 0);
  const deleted =
    (v.events_deleted || 0) +
    (v.reminders_deleted || 0) +
    (v.memories_deleted || 0);
  const total = kept + deleted;
  return {
    status: deleted > 0 ? "partial" : "passed",
    passed: kept,
    failed: deleted,
    warned: v.warned || 0,
    total,
    items: v.items || [],
  };
}

export default function VerifyPage() {
  const [report, setReport] = useState<any>(mapVerify(null));
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState("all");

  const load = async () => {
    const v = await api.verify();
    setReport(mapVerify(v));
  };

  useEffect(() => {
    load();
  }, []);

  const doRun = async () => {
    setRunning(true);
    const v = await api.verify();
    setReport(mapVerify(v));
    setRunning(false);
  };

  const items = report.items.filter((it: any) =>
    filter === "all" ? true : it.status === filter
  );
  const pct = report.total
    ? Math.round((report.passed / report.total) * 100)
    : 0;

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <SectionHeader
        subtitle="verify · /verify"
        title="反幻觉体检"
        icon="fa-shield-check"
        right={
          <>
            <VerifyBadge
              status={report.status}
              count={`${report.passed}/${report.total}`}
            />
            <button
              className={"btn btn-primary " + (running ? "opacity-70" : "")}
              onClick={doRun}
              disabled={running}
            >
              <i className={"fas " + (running ? "fa-spinner fa-spin" : "fa-play")} />{" "}
              {running ? "运行中…" : "运行 run_all"}
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <SummaryCard
          label="通过"
          value={report.passed}
          total={report.total}
          color="green"
          icon="fa-circle-check"
        />
        <SummaryCard
          label="警告"
          value={report.warned}
          total={report.total}
          color="gold"
          icon="fa-triangle-exclamation"
        />
        <SummaryCard
          label="失败"
          value={report.failed}
          total={report.total}
          color="red"
          icon="fa-circle-exclamation"
        />
        <div className="glass p-5">
          <div className="flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-widest text-text-mute">
              通过率
            </div>
            <span className="mono text-[12px] text-text-dim">{pct}%</span>
          </div>
          <div className="mt-4 h-2 rounded-full bg-border-soft overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green to-indigo"
              style={{ width: pct + "%" }}
            />
          </div>
          <div className="mt-2 text-[11px] text-text-mute">
            本次 {report.total} 项 · 不落地 {report.failed} 项需复查
          </div>
        </div>
      </div>

      <div className="glass p-3 mb-4 flex items-center gap-1.5">
        <span className="text-[11px] text-text-mute px-2">FILTER:</span>
        {["all", "passed", "warned", "failed"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={
              "px-3 py-1.5 rounded-md text-[12px] transition " +
              (filter === f
                ? "bg-indigo-soft text-indigo"
                : "text-text-dim hover:bg-bg-elev-2")
            }
          >
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {items.length === 0 && (
          <div className="glass p-6 text-center text-[13px] text-text-dim">
            后端 /verify 返回的是 kept/deleted 计数，暂无明细 item。
          </div>
        )}
        {items.map((it: any) => {
          const statusMap = {
            passed: {
              cls: "border-border-soft",
              icon: "fa-circle-check",
              color: "text-green",
            },
            warned: {
              cls: "border-gold/40",
              icon: "fa-triangle-exclamation",
              color: "text-gold",
            },
            failed: {
              cls: "border-red/50 bg-red/[0.04]",
              icon: "fa-circle-exclamation",
              color: "text-red",
            },
          };
          const status = (it.status as keyof typeof statusMap) || "passed";
          const map = statusMap[status];
          return (
            <div key={it.id} className={"glass p-4 border " + map.cls}>
              <div className="flex items-start gap-3">
                <i className={"fas " + map.icon + " " + map.color + " mt-0.5"} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13.5px] font-medium text-text">
                      {it.kind}
                    </span>
                    <span className="mono text-[11px] text-text-mute">
                      → {it.target}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-[12px]">
                    <div className="p-2 rounded bg-bg-elev-2 border border-border-soft">
                      <div className="text-[10px] uppercase tracking-widest text-text-mute mb-0.5">
                        expected
                      </div>
                      <div className="text-text-dim mono">{it.expected}</div>
                    </div>
                    <div
                      className={
                        "p-2 rounded border " +
                        (it.status === "passed"
                          ? "bg-green/[0.06] border-green/30"
                          : "bg-bg-elev-2 border-border-soft")
                      }
                    >
                      <div className="text-[10px] uppercase tracking-widest text-text-mute mb-0.5">
                        actual
                      </div>
                      <div
                        className={
                          "mono " + (it.status === "failed" ? "text-red" : "text-text")
                        }
                      >
                        {it.actual}
                      </div>
                    </div>
                  </div>
                  {it.hint && (
                    <div className="mt-2 text-[12px] text-gold flex items-start gap-1.5">
                      <i className="fas fa-lightbulb mt-0.5" /> {it.hint}
                    </div>
                  )}
                </div>
                <button className="text-indigo text-[12px] hover:underline shrink-0 mt-0.5">
                  跳源核查 →
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  total,
  color,
  icon,
}: {
  label: string;
  value: number;
  total: number;
  color: "green" | "gold" | "red";
  icon: string;
}) {
  const cls = {
    green: "text-green bg-green-soft",
    gold: "text-gold bg-gold-soft",
    red: "text-red bg-red-soft",
  }[color];
  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between">
        <div className={"w-9 h-9 rounded-lg flex items-center justify-center " + cls}>
          <i className={"fas " + icon} />
        </div>
        <div className="mono text-[11px] text-text-mute">/ {total}</div>
      </div>
      <div className="mt-4 mono text-[28px] font-semibold">{value}</div>
      <div className="mt-1 text-[12px] text-text-dim">{label}</div>
    </div>
  );
}
