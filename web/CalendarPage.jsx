function CalendarPage(){
  const { useState, useEffect } = React;
  const m = window.MockData;
  const [q,setQ] = useState("");
  const [live,setLive] = useState(null);
  const [year,setYear] = useState(new Date().getFullYear());
  const [month,setMonth] = useState(new Date().getMonth());  // 0-indexed

  // q 变化→debounce 直达 /calendar?q=（temporal 范围检索）；空 q 显示全部真事件
  useEffect(()=>{
    if(!q.trim()){ setLive(null); return; }
    const t = setTimeout(async ()=>{
      const j = await window.PA.get("/calendar", { q: q.trim() });
      setLive(j && j.events ? j.events : []);
    }, 400);
    return ()=>clearTimeout(t);
  },[q]);

  const list = live!==null ? live : m.events;

  // dynamic month
  const today = new Date();
  const monthStart = new Date(year, month, 1);
  const startWeekday = monthStart.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for(let i=0;i<startWeekday;i++) cells.push(null);
  for(let d=1;d<=daysInMonth;d++) cells.push(d);
  const eventDays = list.map(e => {
    try { return new Date(e.when_dt).getDate(); } catch(_) { return null; }
  }).filter(Boolean);
  const monthNames = ["一月","二月","三月","四月","五月","六月","七月","八月","九月","十月","十一月","十二月"];
  const isTodayMonth = year===today.getFullYear() && month===today.getMonth();

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="calendar · /calendar?q="
        title="自动日历 · 从转录中确定性提取"
        icon="fa-calendar-days"
        right={<window.DeterministicBadge>when_dt 由 temporal 解析</window.DeterministicBadge>}
      />

      <div className="glass p-4 mb-5 flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[260px] relative">
          <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-mute)] text-[12px]"></i>
          <input className="input pl-9" placeholder='自然语言检索："明天" / "下周五" / "Lily"' value={q} onChange={e=>setQ(e.target.value)} />
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--text-mute)]">
          <span>q 直达后端 /calendar?q=</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Mini calendar */}
        <div className="lg:col-span-2 glass p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[14px] font-semibold">{year} 年 {monthNames[month]}</div>
            <div className="flex items-center gap-1">
              <button onClick={()=>{if(month===0){setYear(y=>y-1);setMonth(11)}else setMonth(m=>m-1)}} className="w-7 h-7 rounded-md hover:bg-[var(--bg-elev-2)] text-[var(--text-dim)]"><i className="fas fa-chevron-left text-[11px]"></i></button>
              <button onClick={()=>{setYear(new Date().getFullYear());setMonth(new Date().getMonth())}} className="w-7 h-7 rounded-md hover:bg-[var(--bg-elev-2)] text-[var(--text-dim)] text-[10px]">今天</button>
              <button onClick={()=>{if(month===11){setYear(y=>y+1);setMonth(0)}else setMonth(m=>m+1)}} className="w-7 h-7 rounded-md hover:bg-[var(--bg-elev-2)] text-[var(--text-dim)]"><i className="fas fa-chevron-right text-[11px]"></i></button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1.5 text-center text-[10.5px] text-[var(--text-mute)] mb-2">
            {["日","一","二","三","四","五","六"].map(d=><div key={d}>{d}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {cells.map((d,i)=>{
              if(!d) return <div key={i}></div>;
              const isToday = isTodayMonth && d===today.getDate();
              const hasEv = eventDays.includes(d);
              return (
                <div key={i} onClick={()=>{const ds=d<10?"0"+d:""+d; const ms=(month+1)<10?"0"+(month+1):""+(month+1); setQ(year+"-"+ms+"-"+ds);}} className={"aspect-square rounded-md flex flex-col items-center justify-center text-[12px] relative "+(isToday?"bg-[var(--indigo)] text-white font-semibold":"text-[var(--text-dim)] hover:bg-[var(--bg-elev-2)] cursor-pointer")}>
                  <span>{d}</span>
                  {hasEv && !isToday && <span className="w-1 h-1 rounded-full bg-[var(--gold)] mt-0.5"></span>}
                  {hasEv && isToday && <span className="w-1 h-1 rounded-full bg-white mt-0.5"></span>}
                </div>
              );
            })}
          </div>

          <div className="mt-5 p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)] text-[12px] text-[var(--text-dim)] leading-5">
            <i className="fas fa-circle-info text-[var(--gold)] mr-1.5"></i>
            日期点为确定性解析得到；点击事件可跳源转录，查看是哪一句话被解析。
          </div>
        </div>

        {/* Events list */}
        <div className="lg:col-span-3 glass p-5">
          <div className="text-[12px] uppercase tracking-[0.22em] text-[var(--text-mute)] mb-3">events · {list.length}</div>
          {list.length===0 ? <window.Empty icon="fa-calendar-xmark" title="没有匹配的事件" /> : (
            <div className="space-y-3">
              {list.map(e=>(
                <div key={e.id} className="p-4 rounded-xl border border-[var(--border-soft)] bg-[var(--bg-elev-2)] hover:border-[#33415A] transition">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-[14px] font-semibold text-[var(--text)]">{e.title}</div>
                      <div className="mt-1.5 flex items-center gap-3 text-[12px] text-[var(--text-dim)] flex-wrap">
                        <span><i className="fas fa-user mr-1"></i>{e.who}</span>
                        <span><i className="fas fa-location-dot mr-1"></i>{e.where}</span>
                      </div>
                    </div>
                    <window.SourceChip type="segment" id={e.source_segment} label={e.source_segment}/>
                  </div>
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-[12px]">
                    <div className="p-2.5 rounded-md bg-[var(--bg)] border border-[var(--border-soft)]">
                      <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)] mb-1">when_raw · 源表达</div>
                      <div className="text-[var(--text)] mono">"{e.when_raw}"</div>
                    </div>
                    <div className="p-2.5 rounded-md bg-[var(--bg)] border border-[rgba(63,182,139,0.3)]">
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)]">when_dt · 解析</div>
                        <window.DeterministicBadge>规则</window.DeterministicBadge>
                      </div>
                      <div className="text-[var(--green)] mono">{e.when_dt}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CalendarPage });
