"use client";

import Link from "next/link";
import type { Memory } from "@/lib/types";

export function TimeChip({ created_at, time_kind = "received", compact = false }: { created_at: string; time_kind?: "received" | "occurred"; compact?: boolean }) {
  const tip = time_kind === "received" ? "记录时间，非真实发生时间" : "事件真实发生时间";
  const color = time_kind === "received" ? "chip-gold" : "chip-green";
  const icon = time_kind === "received" ? "fa-inbox" : "fa-calendar-check";
  return (
    <span className={"chip " + color + " mono"} title={tip}>
      <i className={"fas " + icon} style={{ fontSize: 9 }} />
      {compact ? created_at.slice(5, 16) : created_at}
      <span className="opacity-60">·{time_kind === "received" ? "记录" : "发生"}</span>
    </span>
  );
}

export function SourceChip({ type, id, label }: { type: string; id: string; label?: string }) {
  const palette: Record<string, { color: string; icon: string; text: string }> = {
    segment: { color: "chip-indigo", icon: "fa-waveform-lines", text: "段落" },
    memory: { color: "chip-green", icon: "fa-brain", text: "记忆" },
    persona: { color: "chip-indigo", icon: "fa-user-astronaut", text: "分身" },
    result: { color: "chip-gold", icon: "fa-globe", text: "搜索" },
    event: { color: "chip-indigo", icon: "fa-calendar", text: "事件" },
    wiki: { color: "chip-green", icon: "fa-book", text: "wiki" },
  };
  const p = palette[type] || { color: "", icon: "fa-link", text: type };
  const href = type === "segment" ? `/inbox/?hl=${id}` : type === "memory" ? `/memories/?hl=${id}` : "#";
  return (
    <Link href={href} className={"chip " + p.color + " hover:brightness-125 cursor-pointer mono"} title={"跳源 " + type + ":" + id}>
      <i className={"fas " + p.icon} style={{ fontSize: 9 }} />
      {p.text}:{label || id}
    </Link>
  );
}

export function VerifyBadge({ status = "passed", count }: { status?: "passed" | "failed" | "partial"; count?: string }) {
  const map = {
    passed: { cls: "chip-green", icon: "fa-circle-check", text: "反幻觉 通过" },
    failed: { cls: "chip-red", icon: "fa-circle-exclamation", text: "反幻觉 失败" },
    partial: { cls: "chip-gold", icon: "fa-triangle-exclamation", text: "反幻觉 警告" },
  }[status];
  return (
    <span className={"chip " + map.cls + " mono"} style={{ fontSize: 12, padding: "4px 10px" }}>
      <i className={"fas " + map.icon} />
      {map.text}{count != null ? ` · ${count}` : ""}
    </span>
  );
}

export function DeterministicBadge({ children = "确定性解析" }: { children?: React.ReactNode }) {
  return (
    <span className="chip" style={{ color: "#9DDBC1", background: "rgba(63,182,139,0.10)", borderColor: "rgba(63,182,139,0.35)" }} title="规则解析结果，非 LLM 生成">
      🔒 {children}
    </span>
  );
}

export function GenerativeBadge() {
  return (
    <span className="chip chip-indigo" title="LLM 生成内容，可能存在不确定性">
      <i className="fas fa-sparkles" style={{ fontSize: 9 }} /> LLM 生成
    </span>
  );
}

export function Tag({ children, color = "default" }: { children: React.ReactNode; color?: "default" | "blue" | "green" | "gold" | "red" }) {
  const map = {
    default: "bg-[#1F2533] text-text-dim border-border",
    blue: "bg-indigo-soft text-indigo border-indigo/30",
    green: "bg-green-soft text-green border-green/30",
    gold: "bg-gold-soft text-gold border-gold/30",
    red: "bg-red-soft text-red border-red/30",
  };
  return <span className={"inline-flex items-center px-2 py-0.5 rounded-md text-[11px] border " + map[color]}>{children}</span>;
}

export function SectionHeader({ title, subtitle, right, icon }: { title: string; subtitle: string; right?: React.ReactNode; icon?: string }) {
  return (
    <div className="flex items-end justify-between mb-5">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-text-mute">
          {icon && <i className={"fas " + icon} />}
          <span>{subtitle}</span>
        </div>
        <h1 className="mt-1 text-[22px] font-semibold text-text tracking-tight">{title}</h1>
      </div>
      <div className="flex items-center gap-2">{right}</div>
    </div>
  );
}

export function MemoryCard({ mem }: { mem: Memory }) {
  const kindColor: Record<string, "blue" | "green" | "gold" | "red" | "default"> = {
    event: "blue",
    preference: "green",
    intention: "gold",
    emotion: "red",
  };
  const color = kindColor[mem.kind] || "default";
  const hasEv = !!mem.evidence;
  return (
    <div className="glass card-hover p-4 pad-y">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Tag color={color}>{mem.kind}</Tag>
          <span className="mono text-[11px] text-text-mute">#{mem.id}</span>
        </div>
        {!hasEv && (
          <span className="chip chip-gold" title="缺少 evidence 溯源">
            <i className="fas fa-triangle-exclamation" style={{ fontSize: 9 }} /> 无溯源
          </span>
        )}
      </div>
      <p className="text-[14px] leading-6 text-text">{mem.content}</p>
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {hasEv && <SourceChip type="segment" id={mem.evidence} label={mem.evidence} />}
        </div>
        <TimeChip created_at={mem.created_at} time_kind="received" compact />
      </div>
    </div>
  );
}

export function Stat({ label, value, icon, accent = "indigo", trend, hint }: { label: string; value: React.ReactNode; icon: string; accent?: "indigo" | "green" | "gold" | "red"; trend?: string; hint?: string }) {
  const accentMap = {
    indigo: "text-indigo bg-indigo-soft",
    green: "text-green bg-green-soft",
    gold: "text-gold bg-gold-soft",
    red: "text-red bg-red-soft",
  };
  return (
    <div className="glass p-5 card-hover">
      <div className="flex items-start justify-between">
        <div className={"w-9 h-9 rounded-lg flex items-center justify-center " + accentMap[accent]}>
          <i className={"fas " + icon} />
        </div>
        {trend && <span className="text-[11px] text-text-mute mono">{trend}</span>}
      </div>
      <div className="mt-4 mono text-[28px] font-semibold leading-none text-text">{value}</div>
      <div className="mt-2 text-[12px] text-text-dim">{label}</div>
      {hint && <div className="mt-2 text-[10px] text-text-mute uppercase tracking-widest">{hint}</div>}
    </div>
  );
}

export function Empty({ icon = "fa-ghost", title, hint, action }: { icon?: string; title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="glass p-12 text-center border-dashed">
      <div className="w-14 h-14 rounded-full mx-auto bg-bg-elev-2 flex items-center justify-center text-text-mute text-xl">
        <i className={"fas " + icon} />
      </div>
      <div className="mt-4 text-[15px] text-text">{title}</div>
      {hint && <div className="mt-2 text-[12px] text-text-dim max-w-sm mx-auto">{hint}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
