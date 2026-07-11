function DashboardPage({ onNavigate }){
  const { useState } = React;
  const m = window.MockData;
  const [scanning, setScanning] = useState(false);

  const doScan = async () => {
    setScanning(true);
    const r = await window.PA.post("/interventions/scan");
    if (r) {
      const intr = await window.PA.get("/interventions");
      if (intr && intr.interventions) window.PA.updateMock("interventions", intr.interventions);
    }
    setScanning(false);
  };

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="overview · 2026 · w26"
        title="今日 · 你的助手在替你看着这些"
        icon="fa-grid-2"
        right={
          <>
            <window.VerifyBadge status="partial" count={`${m.verifyReport.passed}/${m.verifyReport.total}`} />
            <button className="btn btn-ghost" onClick={()=>onNavigate("verify")}>
              <i className="fas fa-shield-check"></i> 体检详情
            </button>
            <button className="btn btn-primary" onClick={()=>onNavigate("chat")}>
              <i className="fas fa-comments"></i> 进入对话
            </button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <window.Stat icon="fa-waveform-lines" label="今日新转录段落" value={m.segments.length} accent="indigo" trend="+12%" hint="received" />
        <window.Stat icon="fa-brain"           label="本周记忆增量"   value={m.memories.length} accent="green" trend="+3" hint="evidence 落地 6/7" />
        <window.Stat icon="fa-bell"            label="待触发提醒"    value={m.reminders.filter(r=>!r.fired).length} accent="gold" trend="next 09:00" hint="确定性 when_dt" />
        <window.Stat icon="fa-shield-check"    label="反幻觉通过率"  value={Math.round(m.verifyReport.passed/m.verifyReport.total*100)+"%"} accent={m.verifyReport.failed>0?"red":"green"} trend={m.verifyReport.failed+" failed"} hint="run_all 23 项" />
      </div>

      {/* main two-col */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interventions */}
        <div className="lg:col-span-2 glass p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-mute)]">today · proactive</div>
              <div className="text-[16px] font-semibold mt-1">今日干预 · 主动建议</div>
            </div>
            <button className={"btn btn-ghost text-[12px] "+(scanning?"opacity-70":"")} onClick={doScan} disabled={scanning}>
              <i className={"fas "+(scanning?"fa-spinner fa-spin":"fa-bolt")}></i> {scanning?"扫描中…":"立即扫描触发器"}
            </button>
          </div>

          <div className="space-y-3">
            {m.interventions.map((it, idx) => (
              <div key={it.id} className="group p-4 rounded-xl border border-[var(--border-soft)] hover:border-[#33415A] bg-[var(--bg-elev-2)] transition">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 shrink-0 rounded-lg bg-[var(--indigo-soft)] text-[var(--indigo)] flex items-center justify-center">
                    <i className={"fas "+(it.trigger_kind==="stress_signal"?"fa-wave-pulse":it.trigger_kind==="reading_followup"?"fa-bookmark":"fa-handshake")}></i>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <window.Tag color="blue">{it.trigger_kind}</window.Tag>
                      <window.GenerativeBadge />
                      {!it.delivered && <window.Tag color="gold">未送达</window.Tag>}
                    </div>
                    <p className="mt-2 text-[13.5px] leading-6 text-[var(--text)]">{it.message}</p>
                    <div className="mt-3 flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        {(it.evidence||"").split(",").filter(Boolean).map(e=>(
                          <window.SourceChip key={e} type="memory" id={e.trim()} label={e.trim()} />
                        ))}
                      </div>
                      <div className="flex items-center gap-2">
                        <window.TimeChip created_at={it.created_at} time_kind="received" compact />
                        <button className="text-[12px] text-[var(--indigo)] opacity-0 group-hover:opacity-100 transition">采纳 →</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Health */}
        <div className="glass p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-mute)]">system · health</div>
              <div className="text-[16px] font-semibold mt-1">后端运行状态</div>
            </div>
            <span className="chip chip-green"><i className="fas fa-circle" style={{fontSize:6}}></i> online</span>
          </div>

          <div className="space-y-3">
            {[
              { k:"LLM",       v:m.health.llm,     i:"fa-microchip" },
              { k:"ASR",       v:m.health.asr,     i:"fa-microphone" },
              { k:"Embedder",  v:m.health.embedder,i:"fa-vector-square" },
              { k:"Speaker",   v:m.health.speaker, i:"fa-users" },
              { k:"DB",        v:m.health.db,      i:"fa-database" },
              { k:"Latency",   v:m.health.latency_ms+" ms", i:"fa-gauge" },
            ].map(r=>(
              <div key={r.k} className="flex items-center justify-between py-2 border-b border-[var(--border-soft)] last:border-0">
                <div className="flex items-center gap-2.5 text-[12px] text-[var(--text-dim)]">
                  <i className={"fas "+r.i+" w-4 text-center text-[var(--text-mute)]"}></i>
                  <span>{r.k}</span>
                </div>
                <div className="mono text-[12px] text-[var(--text)]">{r.v}</div>
              </div>
            ))}
          </div>

          <button className="btn btn-ghost w-full justify-center mt-5" onClick={()=>onNavigate("settings")}>
            <i className="fas fa-sliders"></i> 调整 LLM 配置
          </button>
        </div>
      </div>

      {/* recent flow */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[14px] font-semibold">最新接入段落</div>
            <button onClick={()=>onNavigate("inbox")} className="text-[12px] text-[var(--indigo)]">全部 →</button>
          </div>
          <div className="space-y-3">
            {m.segments.slice(0,4).map(s=>(
              <div key={s.id} className="flex gap-3 text-[13px]">
                <span className={"w-6 h-6 shrink-0 rounded-md flex items-center justify-center text-[10px] font-semibold "+(s.speaker==="A"?"bg-[var(--indigo-soft)] text-[var(--indigo)]":"bg-[#222837] text-[var(--text-dim)]")}>{s.speaker}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[var(--text)] leading-5">{s.text}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <window.TimeChip created_at={s.created_at} time_kind={s.time_kind} compact />
                    <span className="mono text-[10px] text-[var(--text-mute)]">{s.source_file}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="text-[14px] font-semibold">未触发提醒</div>
            <button onClick={()=>onNavigate("reminders")} className="text-[12px] text-[var(--indigo)]">全部 →</button>
          </div>
          <div className="space-y-3">
            {m.reminders.filter(r=>!r.fired).map(r=>(
              <div key={r.id} className="p-3 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-elev-2)]">
                <div className="flex items-center justify-between">
                  <div className="text-[13.5px] text-[var(--text)]">{r.what}</div>
                  {r.recurring && <window.Tag color="blue">{r.recurring}</window.Tag>}
                </div>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <span className="mono text-[11px] text-[var(--text-dim)]">原文：{r.when_raw}</span>
                  <window.DeterministicBadge>{r.when_dt}</window.DeterministicBadge>
                  {r.source_segment && <window.SourceChip type="segment" id={r.source_segment} label={r.source_segment} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardPage });
