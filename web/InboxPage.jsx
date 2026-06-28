function InboxPage(){
  const { useState, useMemo, useEffect } = React;
  const m = window.MockData;
  const [selected,setSelected] = useState(null);
  const [filter,setFilter] = useState("all");
  const [scanning,setScanning] = useState(false);

  const doIngest = async ()=>{
    setScanning(true);
    await window.PA.post("/ingest");
    const j = await window.PA.get("/segments");
    if(j && j.segments) window.PA.updateMock("segments", j.segments);
    setScanning(false);
  };
  const doUpload = async (e)=>{
    const f = e.target.files && e.target.files[0];
    if(!f) return;
    await fetch((window.PA_BASE||"")+"/inbox/upload?filename="+encodeURIComponent(f.name),
      { method:"POST", body: await f.text() });
    await doIngest();
    e.target.value = "";
  };

  useEffect(()=>{
    const hl = sessionStorage.getItem("hl_seg");
    if(hl){ setSelected(hl); sessionStorage.removeItem("hl_seg"); }
  },[]);

  const segments = useMemo(()=>{
    if(filter==="all") return m.segments;
    return m.segments.filter(s=>s.speaker===filter);
  },[filter]);

  const relatedMems = (segId) => m.memories.filter(x=>x.segment_id===segId);
  const relatedEvents = (segId) => m.events.filter(x=>x.source_segment===segId);
  const relatedReminders = (segId) => m.reminders.filter(x=>x.source_segment===segId);

  const sel = m.segments.find(s=>s.id===selected);

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="inbox · /segments"
        title="接入转录流"
        icon="fa-inbox"
        right={
          <>
            <input type="file" accept=".txt,.srt" className="hidden" onChange={doUpload} id="inbox-upload" />
            <button className="btn btn-ghost" onClick={()=>document.getElementById("inbox-upload").click()}><i className="fas fa-upload"></i> 上传 .txt / .srt</button>
            <button className={"btn btn-primary "+(scanning?"opacity-70":"")} onClick={doIngest} disabled={scanning}>
              <i className={"fas "+(scanning?"fa-spinner fa-spin":"fa-bolt")}></i>
              {scanning?"扫描中…":"立即扫描 inbox"}
            </button>
          </>
        }
      />

      {/* Speaker legend */}
      <div className="glass p-4 mb-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-[12px]">
          <span className="text-[var(--text-mute)] mr-1">说话人 ·</span>
          {m.speakers.map(s=>(
            <span key={s.name} className={"chip "+(s.name==="A"?"chip-indigo":"")}>
              <i className="fas fa-user-tag" style={{fontSize:9}}></i> {s.name} · {s.label}
            </span>
          ))}
          <span className="ml-2 text-[var(--text-mute)] text-[11px]">来自 TextDiarizer（heuristic）</span>
        </div>
        <div className="flex items-center gap-1 text-[12px]">
          {[{k:"all",t:"全部"},{k:"A",t:"仅我"},{k:"B",t:"仅他人"}].map(f=>(
            <button key={f.k} onClick={()=>setFilter(f.k)} className={"px-3 py-1.5 rounded-md transition "+(filter===f.k?"bg-[var(--indigo-soft)] text-[var(--indigo)]":"text-[var(--text-dim)] hover:bg-[var(--bg-elev-2)]")}>
              {f.t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Timeline */}
        <div className="lg:col-span-3 glass p-5">
          <div className="text-[12px] uppercase tracking-[0.22em] text-[var(--text-mute)] mb-3">timeline · 共 {segments.length} 段</div>
          <div className="space-y-2">
            {segments.map(s=>{
              const isSel = s.id===selected;
              const isUser = s.speaker==="A";
              return (
                <button
                  key={s.id}
                  onClick={()=>setSelected(s.id)}
                  className={"w-full text-left p-3 rounded-lg border transition flex gap-3 "+(isSel?"border-[var(--indigo)] bg-[var(--indigo-soft)]":"border-transparent hover:border-[var(--border)] hover:bg-[var(--bg-elev-2)]")}
                >
                  <span className={"w-7 h-7 shrink-0 rounded-md flex items-center justify-center text-[11px] font-semibold "+(isUser?"bg-[var(--indigo)] text-white":"bg-[#2A3142] text-[var(--text-dim)]")}>{s.speaker}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13.5px] leading-6 text-[var(--text)]">{s.text}</p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      <window.TimeChip created_at={s.created_at} time_kind={s.time_kind} compact />
                      <span className="mono text-[10.5px] text-[var(--text-mute)]">
                        <i className="fas fa-file-lines mr-1"></i>{s.source_file} · {s.start_sec.toFixed(1)}–{s.end_sec.toFixed(1)}s
                      </span>
                      <span className="mono text-[10.5px] text-[var(--text-mute)]">{s.id}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail */}
        <div className="lg:col-span-2 glass p-5 self-start sticky top-6">
          {!sel ? (
            <window.Empty icon="fa-arrow-left-long" title="选中左侧段落查看反查关联" hint="点击任意段落可展开它派生的记忆 / 事件 / 提醒。" />
          ) : (
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-mute)] mb-2">segment · {sel.id}</div>
              <p className="text-[14px] leading-6 text-[var(--text)] bg-[var(--bg-elev-2)] p-3 rounded-md border border-[var(--border-soft)]">"{sel.text}"</p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <window.TimeChip created_at={sel.created_at} time_kind={sel.time_kind} compact />
                <window.Tag>language: {sel.language}</window.Tag>
                <window.Tag>processed: {sel.processed?"yes":"no"}</window.Tag>
              </div>

              <div className="mt-5 space-y-4">
                <InboxBlock icon="fa-brain" title="派生记忆" items={relatedMems(sel.id)} render={mem=>(
                  <window.MemoryCard mem={mem} key={mem.id} />
                )} />
                <InboxBlock icon="fa-calendar" title="派生事件" items={relatedEvents(sel.id)} render={e=>(
                  <div key={e.id} className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                    <div className="text-[13px] text-[var(--text)]">{e.title}</div>
                    <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] text-[var(--text-mute)] mono">原文：{e.when_raw}</span>
                      <window.DeterministicBadge>{e.when_dt}</window.DeterministicBadge>
                    </div>
                  </div>
                )} />
                <Block icon="fa-bell" title="派生提醒" items={relatedReminders(sel.id)} render={r=>(
                  <div key={r.id} className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                    <div className="text-[13px] text-[var(--text)]">{r.what}</div>
                    <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                      <window.DeterministicBadge>{r.when_dt}</window.DeterministicBadge>
                      {r.recurring && <window.Tag color="blue">{r.recurring}</window.Tag>}
                    </div>
                  </div>
                )} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InboxBlock({ icon, title, items, render }){
  return (
    <div>
      <div className="flex items-center gap-2 mb-2 text-[12px] text-[var(--text-dim)]">
        <i className={"fas "+icon}></i> {title} · {items.length}
      </div>
      {items.length===0 ? (
        <div className="text-[12px] text-[var(--text-mute)] italic">无关联</div>
      ) : (
        <div className="space-y-2">{items.map(render)}</div>
      )}
    </div>
  );
}

Object.assign(window, { InboxPage });
