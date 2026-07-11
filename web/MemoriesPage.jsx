function MemoriesPage(){
  const { useState, useEffect, useMemo } = React;
  const m = window.MockData;
  const [q,setQ] = useState("");
  const [kind,setKind] = useState("all");
  const [backendList, setBackendList] = useState(null);

  // search with debounce
  useEffect(()=>{
    if(!q.trim()){ setBackendList(null); return; }
    const t = setTimeout(async ()=>{
      const j = await window.PA.post("/memories/search", { q: q.trim(), limit: 20 });
      if(j && j.memories) setBackendList(j.memories);
    }, 400);
    return ()=>clearTimeout(t);
  },[q]);

  const kinds = ["all","event","preference","intention","emotion"];
  const srcList = backendList !== null ? backendList : m.memories;
  const list = useMemo(()=>{
    return srcList.filter(x=>{
      if(kind!=="all" && x.kind!==kind) return false;
      return true;
    });
  },[kind, srcList]);

  const counts = kinds.reduce((acc,k)=>{
    acc[k] = k==="all"? m.memories.length : m.memories.filter(x=>x.kind===k).length;
    return acc;
  },{});

  const evidenceLanded = m.memories.filter(x=>x.evidence).length;

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="memory · /memories"
        title="记忆库 · 语义可检索"
        icon="fa-brain"
        right={<span className="text-[12px] text-[var(--text-dim)]">共 {m.memories.length} 条 · evidence 落地 {evidenceLanded}/{m.memories.length}</span>}
      />

      <div className="glass p-4 mb-5">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 min-w-[260px] relative">
            <i className="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-mute)] text-[12px]"></i>
            <input className="input pl-9" placeholder="语义检索（如：阅读 / Lily / 喂药）" value={q} onChange={e=>setQ(e.target.value)} />
          </div>
          <div className="flex items-center gap-1.5">
            {kinds.map(k=>(
              <button key={k} onClick={()=>setKind(k)} className={"px-3 py-1.5 rounded-md text-[12px] transition "+(kind===k?"bg-[var(--indigo-soft)] text-[var(--indigo)] border border-[rgba(91,141,239,0.3)]":"text-[var(--text-dim)] border border-transparent hover:border-[var(--border)]")}>
                {k} <span className="opacity-60 mono ml-1">{counts[k]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {list.length===0 ? (
        <window.Empty icon="fa-magnifying-glass-minus" title="没找到匹配的记忆" hint="试试改关键词或清空筛选。"/>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {list.map(mem=><window.MemoryCard key={mem.id} mem={mem} />)}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { MemoriesPage });
