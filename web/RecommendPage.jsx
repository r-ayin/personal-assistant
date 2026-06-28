function RecommendPage(){
  const { useState, useEffect } = React;
  const m = window.MockData;
  const [kind,setKind] = useState("book");
  const [q,setQ] = useState("");

  // 切 kind 时按需拉真推荐（含可选 query）；失败保留 bootstrap/mock 数据
  useEffect(()=>{
    (async ()=>{
      const j = await window.PA.get("/recommend", { kind, ...(q?{q}:{}) });
      if(j && j.recommendations){
        const next = Object.assign({}, m.recommendations);
        next[kind] = j.recommendations.map(r=>({item:r.item, reason:r.reason, based_on: r.based_on?[r.based_on]:[], from_search: kind!=="action"}));
        window.PA.updateMock("recommendations", next);
      }
    })();
  },[kind]);

  const kinds = [
    { k:"book",   t:"图书", icon:"fa-book" },
    { k:"movie",  t:"影片", icon:"fa-film" },
    { k:"action", t:"行动", icon:"fa-bolt" },
  ];
  const items = m.recommendations[kind] || [];

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="recommend · /recommend"
        title="推荐引擎"
        icon="fa-sparkles"
        right={<>
          <window.GenerativeBadge />
          <window.Tag color="green">based_on 必须落地</window.Tag>
        </>}
      />

      <div className="glass p-4 mb-5 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-1.5">
          {kinds.map(it=>(
            <button key={it.k} onClick={()=>setKind(it.k)} className={"px-3 py-2 rounded-md text-[12.5px] transition flex items-center gap-1.5 "+(kind===it.k?"bg-[var(--indigo-soft)] text-[var(--indigo)] border border-[rgba(91,141,239,0.3)]":"text-[var(--text-dim)] border border-transparent hover:border-[var(--border)]")}>
              <i className={"fas "+it.icon}></i> {it.t}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-[360px] min-w-[200px]">
          <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-mute)] text-[12px]"></i>
          <input className="input pl-9" placeholder="可选 query（缩窄推荐范围）" value={q} onChange={e=>setQ(e.target.value)} />
        </div>
      </div>

      {items.length===0 ? (
        <window.Empty icon="fa-ghost" title="暂无推荐" hint="后端会基于联网搜索 + persona 维度生成；无落地结果时不展示假数据。" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((it,idx)=>(
            <div key={idx} className="glass card-hover p-5 flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--gold-soft)] text-[var(--gold)] flex items-center justify-center">
                  <i className={"fas "+(kind==="book"?"fa-book-bookmark":kind==="movie"?"fa-clapperboard":"fa-bolt-lightning")}></i>
                </div>
                {it.from_search && <span className="chip chip-indigo"><i className="fas fa-globe" style={{fontSize:9}}></i> 联网搜索</span>}
              </div>
              <div className="text-[14.5px] font-semibold text-[var(--text)] leading-snug">{it.item}</div>
              <p className="mt-2 text-[12.5px] text-[var(--text-dim)] leading-5 flex-1">{it.reason}</p>
              <div className="mt-3 pt-3 border-t border-[var(--border-soft)]">
                <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)] mb-1.5">based_on</div>
                <div className="flex flex-wrap gap-1.5">
                  {it.based_on.map(b=>{
                    const [type,id] = b.split(":");
                    return <window.SourceChip key={b} type={type==="mem"?"memory":type} id={id} label={id}/>;
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { RecommendPage });
