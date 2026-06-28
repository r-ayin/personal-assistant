// 横切复用：TimeChip / SourceChip / VerifyBadge / DeterministicBadge / MemoryCard / SectionHeader / Tag
const Chips = (() => {
  const { useState } = React;

  function TimeChip({ created_at, time_kind = "received", compact = false }){
    const tip = time_kind === "received"
      ? "记录时间，非真实发生时间"
      : "事件真实发生时间";
    const color = time_kind === "received" ? "chip-gold" : "chip-green";
    const icon = time_kind === "received" ? "fa-inbox" : "fa-calendar-check";
    return (
      <span className={"chip "+color+" mono"} title={tip}>
        <i className={"fas "+icon} style={{fontSize:9}}></i>
        {compact ? created_at.slice(5,16) : created_at}
        <span className="opacity-60">·{time_kind==="received"?"记录":"发生"}</span>
      </span>
    );
  }

  function SourceChip({ type, id, label }){
    const palette = {
      segment:  { color:"chip-indigo", icon:"fa-waveform-lines", text:"段落" },
      memory:   { color:"chip-green",  icon:"fa-brain",          text:"记忆" },
      persona:  { color:"chip-indigo", icon:"fa-user-astronaut", text:"分身" },
      result:   { color:"chip-gold",   icon:"fa-globe",          text:"搜索" },
      event:    { color:"chip-indigo", icon:"fa-calendar",       text:"事件" },
      wiki:     { color:"chip-green",  icon:"fa-book",           text:"wiki"},
    }[type] || { color:"", icon:"fa-link", text:type };
    const click = () => window.dispatchEvent(new CustomEvent("source-jump",{detail:{type,id}}));
    return (
      <button onClick={click} className={"chip "+palette.color+" hover:brightness-125 cursor-pointer mono"} title={"跳源 "+type+":"+id}>
        <i className={"fas "+palette.icon} style={{fontSize:9}}></i>
        {palette.text}:{label||id}
      </button>
    );
  }

  function VerifyBadge({ status="passed", count }){
    const map = {
      passed:  { cls:"chip-green", icon:"fa-circle-check",     text:"反幻觉 通过" },
      failed:  { cls:"chip-red",   icon:"fa-circle-exclamation", text:"反幻觉 失败"  },
      partial: { cls:"chip-gold",  icon:"fa-triangle-exclamation", text:"反幻觉 警告"},
    }[status];
    return (
      <span className={"chip "+map.cls+" mono"} style={{fontSize:12,padding:"4px 10px"}}>
        <i className={"fas "+map.icon}></i>
        {map.text}{count!=null?` · ${count}`:""}
      </span>
    );
  }

  function DeterministicBadge({ children="确定性解析" }){
    return (
      <span className="chip" style={{color:"#9DDBC1",background:"rgba(63,182,139,0.10)",borderColor:"rgba(63,182,139,0.35)"}} title="规则解析结果，非 LLM 生成">
        🔒 {children}
      </span>
    );
  }

  function GenerativeBadge(){
    return (
      <span className="chip chip-indigo" title="LLM 生成内容，可能存在不确定性">
        <i className="fas fa-sparkles" style={{fontSize:9}}></i> LLM 生成
      </span>
    );
  }

  function Tag({ children, color="default" }){
    const map = {
      default: "bg-[#1F2533] text-[var(--text-dim)] border-[var(--border)]",
      blue: "bg-[var(--indigo-soft)] text-[var(--indigo)] border-[rgba(91,141,239,0.3)]",
      green: "bg-[var(--green-soft)] text-[var(--green)] border-[rgba(63,182,139,0.3)]",
      gold: "bg-[var(--gold-soft)] text-[var(--gold)] border-[rgba(224,164,88,0.3)]",
      red: "bg-[var(--red-soft)] text-[var(--red)] border-[rgba(224,88,79,0.3)]",
    };
    return <span className={"inline-flex items-center px-2 py-0.5 rounded-md text-[11px] border "+map[color]}>{children}</span>;
  }

  function SectionHeader({ title, subtitle, right, icon }){
    return (
      <div className="flex items-end justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-[var(--text-mute)]">
            {icon && <i className={"fas "+icon}></i>}
            <span>{subtitle}</span>
          </div>
          <h1 className="mt-1 text-[22px] font-semibold text-[var(--text)] tracking-tight">{title}</h1>
        </div>
        <div className="flex items-center gap-2">{right}</div>
      </div>
    );
  }

  function MemoryCard({ mem, onJumpSegment }){
    const kindColor = { event:"blue", preference:"green", intention:"gold", emotion:"red" }[mem.kind] || "default";
    const hasEv = !!mem.evidence;
    return (
      <div className="glass card-hover p-4 pad-y">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Tag color={kindColor}>{mem.kind}</Tag>
            <span className="mono text-[11px] text-[var(--text-mute)]">#{mem.id}</span>
          </div>
          {!hasEv && (
            <span className="chip chip-gold" title="缺少 evidence 溯源">
              <i className="fas fa-triangle-exclamation" style={{fontSize:9}}></i> 无溯源
            </span>
          )}
        </div>
        <p className="text-[14px] leading-6 text-[var(--text)]">{mem.content}</p>
        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            {hasEv && <SourceChip type="segment" id={mem.evidence} label={mem.evidence}/>}
          </div>
          <TimeChip created_at={mem.created_at} time_kind="received" compact/>
        </div>
      </div>
    );
  }

  function Stat({ label, value, icon, accent="indigo", trend, hint }){
    const accentMap = {
      indigo:"text-[var(--indigo)] bg-[var(--indigo-soft)]",
      green:"text-[var(--green)] bg-[var(--green-soft)]",
      gold:"text-[var(--gold)] bg-[var(--gold-soft)]",
      red:"text-[var(--red)] bg-[var(--red-soft)]",
    }[accent];
    return (
      <div className="glass p-5 card-hover">
        <div className="flex items-start justify-between">
          <div className={"w-9 h-9 rounded-lg flex items-center justify-center "+accentMap}>
            <i className={"fas "+icon}></i>
          </div>
          {trend && <span className="text-[11px] text-[var(--text-mute)] mono">{trend}</span>}
        </div>
        <div className="mt-4 mono text-[28px] font-semibold leading-none text-[var(--text)]">{value}</div>
        <div className="mt-2 text-[12px] text-[var(--text-dim)]">{label}</div>
        {hint && <div className="mt-2 text-[10px] text-[var(--text-mute)] uppercase tracking-widest">{hint}</div>}
      </div>
    );
  }

  function Empty({ icon="fa-ghost", title, hint, action }){
    return (
      <div className="glass p-12 text-center border-dashed">
        <div className="w-14 h-14 rounded-full mx-auto bg-[var(--bg-elev-2)] flex items-center justify-center text-[var(--text-mute)] text-xl">
          <i className={"fas "+icon}></i>
        </div>
        <div className="mt-4 text-[15px] text-[var(--text)]">{title}</div>
        {hint && <div className="mt-2 text-[12px] text-[var(--text-dim)] max-w-sm mx-auto">{hint}</div>}
        {action && <div className="mt-5">{action}</div>}
      </div>
    );
  }

  return { TimeChip, SourceChip, VerifyBadge, DeterministicBadge, GenerativeBadge, Tag, SectionHeader, MemoryCard, Stat, Empty };
})();

Object.assign(window, Chips);
