function WikiPage(){
  const { useState, useMemo } = React;
  const m = window.MockData;
  const [tag,setTag] = useState("all");
  const [q,setQ] = useState("");
  const [activeId,setActiveId] = useState(m.wikiPages[0].id);
  const [building,setBuilding] = useState(false);

  const allTags = useMemo(()=>{
    const s = new Set();
    m.wikiPages.forEach(p=> {
      const tags = Array.isArray(p.tags) ? p.tags : (p.tags||"").split(",").map(t=>t.trim());
      tags.forEach(t=> t && s.add(t));
    });
    return ["all", ...Array.from(s)];
  },[]);

  const filtered = m.wikiPages.filter(p=>{
    const ptags = Array.isArray(p.tags) ? p.tags : (p.tags||"").split(",").map(x=>x.trim());
    if(tag!=="all" && !ptags.includes(tag)) return false;
    if(q && !(p.title.includes(q) || p.body.includes(q))) return false;
    return true;
  });

  const active = m.wikiPages.find(p=>p.id===activeId) || filtered[0];

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="wiki · /wiki"
        title="个人 wiki · 增量构建"
        icon="fa-book"
        right={<>
          <span className="text-[12px] text-[var(--text-dim)]">{m.wikiPages.length} 篇</span>
          <button className={"btn btn-primary "+(building?"opacity-70":"")} onClick={async()=>{setBuilding(true); await window.PA.post("/wiki/build"); const j=await window.PA.get("/wiki"); if(j&&j.pages) window.PA.updateMock("wikiPages",j.pages); setBuilding(false);}} disabled={building}>
            <i className={"fas "+(building?"fa-spinner fa-spin":"fa-hammer")}></i> {building?"构建中…":"增量构建"}
          </button>
        </>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Tag cloud + list */}
        <div className="lg:col-span-1 space-y-4">
          <div className="glass p-4">
            <div className="text-[11px] uppercase tracking-widest text-[var(--text-mute)] mb-2">标签云</div>
            <div className="flex flex-wrap gap-1.5">
              {allTags.map(t=>(
                <button key={t} onClick={()=>setTag(t)} className={"px-2.5 py-1 rounded-md text-[11.5px] transition "+(tag===t?"bg-[var(--indigo-soft)] text-[var(--indigo)] border border-[rgba(91,141,239,0.3)]":"bg-[var(--bg-elev-2)] text-[var(--text-dim)] border border-transparent hover:text-[var(--text)]")}>
                  #{t}
                </button>
              ))}
            </div>
          </div>

          <div className="glass p-4">
            <div className="relative mb-3">
              <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-mute)] text-[11px]"></i>
              <input className="input pl-9 text-[12px]" placeholder="搜索 wiki…" value={q} onChange={e=>setQ(e.target.value)} />
            </div>
            <div className="space-y-1">
              {filtered.map(p=>(
                <button key={p.id} onClick={()=>setActiveId(p.id)} className={"w-full text-left px-3 py-2 rounded-md text-[12.5px] transition "+(active && active.id===p.id?"bg-[var(--indigo-soft)] text-[var(--indigo)]":"text-[var(--text-dim)] hover:bg-[var(--bg-elev-2)] hover:text-[var(--text)]")}>
                  <div className="truncate">{p.title}</div>
                  <div className="mono text-[10px] text-[var(--text-mute)] mt-0.5">{p.created_at.slice(0,10)}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Page detail */}
        <div className="lg:col-span-3">
          {active ? (
            <div className="glass p-7">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-[var(--text-mute)] mb-2">{active.id}</div>
                  <h2 className="text-[22px] font-semibold tracking-tight">{active.title}</h2>
                </div>
                <window.TimeChip created_at={active.created_at} time_kind="received" compact />
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {(Array.isArray(active.tags) ? active.tags : (active.tags||"").split(",").filter(Boolean)).map(t =><window.Tag key={t} color="blue">#{t.trim()}</window.Tag>)}
              </div>

              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-5">
                <div className="md:col-span-2">
                  <p className="text-[14px] leading-7 text-[var(--text)] whitespace-pre-wrap">{active.body}</p>
                </div>
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                    <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)] mb-2">落地源记忆 · {active.source_ids.split(",").filter(Boolean).length}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {active.source_ids.split(",").filter(Boolean).map(id=>(
                        <window.SourceChip key={id} type="memory" id={id.trim()} label={id.trim()}/>
                      ))}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                    <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)] mb-2">页内互链</div>
                    {active.link_ids ? (
                      <div className="flex flex-wrap gap-1.5">
                        {active.link_ids.split(",").filter(Boolean).map(id=>{
                          const target = m.wikiPages.find(p=>p.id===id.trim());
                          return (
                            <button key={id} onClick={()=>setActiveId(id.trim())} className="chip chip-green hover:brightness-125">
                              <i className="fas fa-link" style={{fontSize:9}}></i> {target ? target.title : id}
                            </button>
                          );
                        })}
                      </div>
                    ) : <div className="text-[11px] text-[var(--text-mute)] italic">无互链</div>}
                  </div>
                </div>
              </div>
            </div>
          ) : <window.Empty icon="fa-book-open" title="没有匹配的 wiki 页" />}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { WikiPage });
