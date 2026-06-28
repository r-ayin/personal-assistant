function RemindersPage(){
  const { useState } = React;
  const m = window.MockData;
  const [checking,setChecking] = useState(false);

  const pending = m.reminders.filter(r=>!r.fired);
  const fired = m.reminders.filter(r=>r.fired);

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="reminders · /reminders"
        title="定时提醒"
        icon="fa-bell"
        right={<>
          <span className="text-[12px] text-[var(--text-dim)]">{pending.length} 待发 · {fired.length} 已发</span>
          <button className={"btn btn-primary "+(checking?"opacity-70":"")} onClick={async()=>{setChecking(true); await window.PA.post("/reminders/check"); const j=await window.PA.get("/reminders"); if(j&&j.reminders) window.PA.updateMock("reminders",j.reminders); setChecking(false);}} disabled={checking}>
            <i className={"fas "+(checking?"fa-spinner fa-spin":"fa-stopwatch")}></i> {checking?"检查中…":"立即检查到点"}
          </button>
        </>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Column title="待触发" icon="fa-clock" tone="indigo" items={pending} empty="暂无待触发提醒。" />
        <Column title="已触发" icon="fa-circle-check" tone="green" items={fired} empty="还没有触发记录。" />
      </div>

      <div className="mt-6 glass p-4 text-[12px] text-[var(--text-dim)] flex items-start gap-2">
        <i className="fas fa-shield-halved text-[var(--green)] mt-0.5"></i>
        <div>
          所有 <span className="text-[var(--text)]">when_dt</span> 由 <span className="mono">temporal.resolve</span> 确定性解析得到（🔒），与 LLM 生成内容视觉区分。Android 端命中 fired 走本地通知通道；Web 仅展示。
        </div>
      </div>
    </div>
  );
}

function Column({ title, icon, tone, items, empty }){
  const toneCls = { indigo:"text-[var(--indigo)]", green:"text-[var(--green)]" }[tone];
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 mb-4">
        <i className={"fas "+icon+" "+toneCls}></i>
        <div className="text-[14px] font-semibold">{title}</div>
        <span className="ml-1 text-[11px] text-[var(--text-mute)] mono">{items.length}</span>
      </div>
      {items.length===0 ? <div className="text-[12px] text-[var(--text-mute)] italic py-6 text-center">{empty}</div> : (
        <div className="space-y-3">
          {items.map(r=>(
            <div key={r.id} className="p-4 rounded-xl border border-[var(--border-soft)] bg-[var(--bg-elev-2)]">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[13.5px] text-[var(--text)] flex-1">{r.what}</div>
                {r.recurring && <window.Tag color="blue">{r.recurring}</window.Tag>}
                {r.fired ? <window.Tag color="green">已触发</window.Tag> : <window.Tag color="gold">待发</window.Tag>}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[11.5px]">
                <div className="p-2 rounded-md bg-[var(--bg)] border border-[var(--border-soft)]">
                  <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)]">when_raw</div>
                  <div className="text-[var(--text-dim)] mono mt-0.5">"{r.when_raw||"—"}"</div>
                </div>
                <div className="p-2 rounded-md bg-[var(--bg)] border border-[rgba(63,182,139,0.3)]">
                  <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)]">when_dt 🔒</div>
                  <div className="text-[var(--green)] mono mt-0.5">{r.when_dt}</div>
                </div>
              </div>
              {r.source_segment && (
                <div className="mt-3 flex items-center gap-2">
                  <window.SourceChip type="segment" id={r.source_segment} label={r.source_segment}/>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { RemindersPage });
