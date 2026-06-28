function PersonaPage(){
  const { useState } = React;
  const m = window.MockData;
  const [version,setVersion] = useState(m.persona.version);
  const [distilling,setDistilling] = useState(false);

  const dims = Object.entries(m.persona.profile);

  // polygon points for radar
  const cx=170, cy=170, r=130;
  const N = dims.length;
  const points = dims.map(([k,v],i)=>{
    const angle = (Math.PI*2*i)/N - Math.PI/2;
    const rad = r*v.score;
    return [cx + Math.cos(angle)*rad, cy + Math.sin(angle)*rad];
  });
  const polyPts = points.map(p=>p.join(",")).join(" ");
  const labels = dims.map(([k,v],i)=>{
    const angle = (Math.PI*2*i)/N - Math.PI/2;
    return {
      k,
      x: cx + Math.cos(angle)*(r+22),
      y: cy + Math.sin(angle)*(r+22) + 4,
      anchor: Math.abs(Math.cos(angle))<0.3 ? "middle" : (Math.cos(angle)>0 ? "start":"end"),
    };
  });

  const dimNameMap = {
    identity:"身份", values:"价值观", cognition:"认知风格", preferences:"偏好",
    relationships:"关系", goals:"目标", emotionalStyle:"情感风格", knowledgeAreas:"知识领域",
  };

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle={`persona · v${version}`}
        title="数字分身 · 八维蒸馏"
        icon="fa-user-astronaut"
        right={<>
          <select className="input w-auto" value={version} onChange={e=>setVersion(+e.target.value)}>
            {m.persona.versions.map(v=>(<option key={v.v} value={v.v}>v{v.v} · {v.at.slice(5,10)}</option>))}
          </select>
          <button className={"btn btn-primary "+(distilling?"opacity-70":"")} onClick={async()=>{setDistilling(true); await window.PA.post("/distill"); const p=await window.PA.get("/profile"); if(p && window.PA.mapPersona){ const pm=window.PA.mapPersona(p); pm.versions=m.persona.versions||[]; window.PA.updateMock("persona", Object.assign({}, m.persona, pm)); setVersion(pm.version); } setDistilling(false);}} disabled={distilling}>
            <i className={"fas "+(distilling?"fa-spinner fa-spin":"fa-flask")}></i> {distilling?"蒸馏中…":"重新蒸馏"}
          </button>
        </>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Radar */}
        <div className="lg:col-span-2 glass p-6">
          <div className="text-[12px] uppercase tracking-[0.22em] text-[var(--text-mute)] mb-3">八维雷达 · score 0–1</div>
          <svg viewBox="0 0 340 340" width="100%" className="radar-grid">
            {[0.25,0.5,0.75,1].map((k,i)=>(
              <circle key={i} cx={cx} cy={cy} r={r*k} />
            ))}
            {dims.map((_,i)=>{
              const angle = (Math.PI*2*i)/N - Math.PI/2;
              return <line key={i} x1={cx} y1={cy} x2={cx+Math.cos(angle)*r} y2={cy+Math.sin(angle)*r} />;
            })}
            <polygon points={polyPts} className="radar-area" />
            {points.map((p,i)=><circle key={i} cx={p[0]} cy={p[1]} r={3} fill="var(--indigo)" />)}
            {labels.map(l=>(
              <text key={l.k} x={l.x} y={l.y} className="radar-label" textAnchor={l.anchor}>{dimNameMap[l.k]||l.k}</text>
            ))}
          </svg>

          <div className="mt-4 p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
            <div className="text-[11px] text-[var(--text-mute)] uppercase tracking-widest">change summary · v{version}</div>
            <p className="text-[13px] mt-1.5 text-[var(--text)] leading-6">{m.persona.change_summary}</p>
          </div>
        </div>

        {/* Dimensions */}
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {dims.map(([k,v])=>(
            <div key={k} className="glass card-hover p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-mute)]">{k}</div>
                  <div className="text-[14px] font-semibold mt-1 text-[var(--text)]">{dimNameMap[k]||k}</div>
                </div>
                <div className="mono text-[12px] text-[var(--indigo)]">{(v.score*100).toFixed(0)}</div>
              </div>
              <div className="h-1 rounded-full bg-[var(--border-soft)] mt-3 overflow-hidden">
                <div className="h-full bg-[var(--indigo)]" style={{width: (v.score*100)+"%"}}></div>
              </div>
              <p className="mt-3 text-[12.5px] text-[var(--text-dim)] leading-5">{v.summary}</p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <span className="text-[10.5px] text-[var(--text-mute)]">基于 {v.evidence.length} 条记忆</span>
                {v.evidence.map(e=>(
                  <window.SourceChip key={e} type="memory" id={e} label={e}/>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PersonaPage });
