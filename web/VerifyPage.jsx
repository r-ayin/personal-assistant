function VerifyPage(){
  const { useState } = React;
  const m = window.MockData;
  const r = m.verifyReport;
  const [running,setRunning] = useState(false);
  const [filter,setFilter] = useState("all");
  const statusFilter = (s) => filter==="all" ? true : s===filter;
  const items = r.items.filter(x=>statusFilter(x.status));

  const pct = r.total ? Math.round(r.passed/r.total*100) : 0;

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="verify · /verify"
        title="反幻觉体检"
        icon="fa-shield-check"
        right={<>
          <window.VerifyBadge status={r.status} count={`${r.passed}/${r.total}`} />
          <button className={"btn btn-primary "+(running?"opacity-70":"")} onClick={async()=>{setRunning(true); const v=await window.PA.post("/verify"); if(v && window.PA.mapVerify) window.PA.updateMock("verifyReport", window.PA.mapVerify(v)); setRunning(false);}} disabled={running}>
            <i className={"fas "+(running?"fa-spinner fa-spin":"fa-play")}></i> {running?"运行中…":"运行 run_all"}
          </button>
        </>}
      />

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <SummaryCard label="通过" value={r.passed} total={r.total} color="green" icon="fa-circle-check" />
        <SummaryCard label="警告" value={r.warned} total={r.total} color="gold"  icon="fa-triangle-exclamation" />
        <SummaryCard label="失败" value={r.failed} total={r.total} color="red"   icon="fa-circle-exclamation" />
        <div className="glass p-5">
          <div className="flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-widest text-[var(--text-mute)]">通过率</div>
            <span className="mono text-[12px] text-[var(--text-dim)]">{pct}%</span>
          </div>
          <div className="mt-4 h-2 rounded-full bg-[var(--border-soft)] overflow-hidden">
            <div className="h-full bg-gradient-to-r from-[var(--green)] to-[var(--indigo)]" style={{width:pct+"%"}}></div>
          </div>
          <div className="mt-2 text-[11px] text-[var(--text-mute)]">本次 {r.total} 项 · 不落地 {r.failed} 项需复查</div>
        </div>
      </div>

      {/* Filter */}
      <div className="glass p-3 mb-4 flex items-center gap-1.5">
        <span className="text-[11px] text-[var(--text-mute)] px-2">FILTER:</span>
        {["all","passed","warned","failed"].map(f=>(
          <button key={f} onClick={()=>setFilter(f)} className={"px-3 py-1.5 rounded-md text-[12px] transition "+(filter===f?"bg-[var(--indigo-soft)] text-[var(--indigo)]":"text-[var(--text-dim)] hover:bg-[var(--bg-elev-2)]")}>
            {f}
          </button>
        ))}
      </div>

      {/* Items */}
      <div className="space-y-2">
        {items.map(it=>{
          const map = {
            passed: { cls:"border-[var(--border-soft)]",                icon:"fa-circle-check",        color:"text-[var(--green)]" },
            warned: { cls:"border-[rgba(224,164,88,0.4)]",              icon:"fa-triangle-exclamation",color:"text-[var(--gold)]" },
            failed: { cls:"border-[rgba(224,88,79,0.5)] bg-[rgba(224,88,79,0.04)]", icon:"fa-circle-exclamation", color:"text-[var(--red)]" },
          }[it.status];
          return (
            <div key={it.id} className={"glass p-4 border "+map.cls}>
              <div className="flex items-start gap-3">
                <i className={"fas "+map.icon+" "+map.color+" mt-0.5"}></i>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13.5px] font-medium text-[var(--text)]">{it.kind}</span>
                    <span className="mono text-[11px] text-[var(--text-mute)]">→ {it.target}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-[12px]">
                    <div className="p-2 rounded bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                      <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)] mb-0.5">expected</div>
                      <div className="text-[var(--text-dim)] mono">{it.expected}</div>
                    </div>
                    <div className={"p-2 rounded border "+(it.status==="passed"?"bg-[rgba(63,182,139,0.06)] border-[rgba(63,182,139,0.3)]":"bg-[var(--bg-elev-2)] border-[var(--border-soft)]")}>
                      <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)] mb-0.5">actual</div>
                      <div className={"mono "+(it.status==="failed"?"text-[var(--red)]":"text-[var(--text)]")}>{it.actual}</div>
                    </div>
                  </div>
                  {it.hint && (
                    <div className="mt-2 text-[12px] text-[var(--gold)] flex items-start gap-1.5">
                      <i className="fas fa-lightbulb mt-0.5"></i> {it.hint}
                    </div>
                  )}
                </div>
                <button className="text-[var(--indigo)] text-[12px] hover:underline shrink-0 mt-0.5">
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

function SummaryCard({ label, value, total, color, icon }){
  const cls = { green:"text-[var(--green)] bg-[var(--green-soft)]", gold:"text-[var(--gold)] bg-[var(--gold-soft)]", red:"text-[var(--red)] bg-[var(--red-soft)]" }[color];
  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between">
        <div className={"w-9 h-9 rounded-lg flex items-center justify-center "+cls}>
          <i className={"fas "+icon}></i>
        </div>
        <div className="mono text-[11px] text-[var(--text-mute)]">/ {total}</div>
      </div>
      <div className="mt-4 mono text-[28px] font-semibold">{value}</div>
      <div className="mt-1 text-[12px] text-[var(--text-dim)]">{label}</div>
    </div>
  );
}

Object.assign(window, { VerifyPage });
