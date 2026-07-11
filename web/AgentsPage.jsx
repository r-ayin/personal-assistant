function AgentsPage(){
  const { useState, useEffect } = React;
  const m = window.MockData;
  const [agents, setAgents] = useState(m.agents || []);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [personality, setPersonality] = useState("");

  const refresh = async () => {
    const j = await window.PA.get("/agents");
    if (j && j.agents) {
      setAgents(j.agents);
      window.PA.updateMock("agents", j.agents);
    }
  };

  useEffect(() => { refresh(); }, []);

  const saveAgent = async (a) => {
    const updates = {};
    if (name) updates.name = name;
    if (personality) updates.personality = personality;
    await window.PA.put("/agents/" + a.id, updates);
    setEditing(null);
    setName("");
    setPersonality("");
    await refresh();
  };

  const onlineCount = agents.filter(a => a.enabled).length;

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="agents · /agents"
        title="设备管理 · 多 Agent 配置"
        icon="fa-microchip"
        right={<span className="text-[12px] text-[var(--text-dim)]">{agents.length} 设备 · {onlineCount} 在线</span>}
      />

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="glass p-5">
          <div className="mono text-[28px] font-semibold text-[var(--text)]">{agents.length}</div>
          <div className="mt-2 text-[12px] text-[var(--text-dim)]">注册设备数</div>
        </div>
        <div className="glass p-5">
          <div className="mono text-[28px] font-semibold text-[var(--green)]">{onlineCount}</div>
          <div className="mt-2 text-[12px] text-[var(--text-dim)]">启用中</div>
        </div>
        <div className="glass p-5">
          <div className="mono text-[28px] font-semibold text-[var(--indigo)]">1</div>
          <div className="mt-2 text-[12px] text-[var(--text-dim)]">统一后端 · DeepSeek</div>
        </div>
      </div>

      {/* Agent list */}
      <div className="space-y-4">
        {agents.length === 0 ? (
          <window.Empty icon="fa-microchip" title="暂无设备" hint="ESP32 配网后会自动注册到这里。" />
        ) : agents.map(a => (
          <div key={a.id} className="glass p-5 card-hover">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={"w-12 h-12 rounded-xl flex items-center justify-center text-lg " + (a.enabled ? "bg-[var(--green-soft)] text-[var(--green)]" : "bg-[var(--bg-elev-2)] text-[var(--text-mute)]")}>
                  <i className="fas fa-microchip"></i>
                </div>
                <div>
                  <div className="text-[16px] font-semibold text-[var(--text)]">{a.name}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={"chip " + (a.enabled ? "chip-green" : "chip")}>
                      <i className={"fas fa-circle"} style={{fontSize:6}}></i> {a.enabled ? "在线" : "离线"}
                    </span>
                    <span className="mono text-[11px] text-[var(--text-mute)]">{a.id}</span>
                    <span className="mono text-[11px] text-[var(--text-mute)]">uuid: {a.device_uuid}</span>
                  </div>
                </div>
              </div>
              <button onClick={() => { setEditing(a); setName(a.name); setPersonality(a.personality); }}
                      className="btn btn-ghost"><i className="fas fa-pen"></i> 配置</button>
            </div>

            {/* Personality preview */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)] mb-1">Voice</div>
                <div className="text-[13px] text-[var(--text)]">{a.voice || "default"}</div>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                <div className="text-[10px] uppercase tracking-widest text-[var(--text-mute)] mb-1">Personality</div>
                <div className="text-[13px] text-[var(--text-dim)] mono" style={{fontSize:11}}>
                  {a.personality && a.personality !== "{}" ? a.personality : "（默认）"}
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="mt-4 flex items-center gap-4 text-[12px] text-[var(--text-dim)]">
              <span><i className="fas fa-brain mr-1"></i>记忆: 统一池</span>
              <span><i className="fas fa-database mr-1"></i>存储: 统一 SQLite</span>
              <span><i className="fas fa-microchip mr-1"></i>LLM: DeepSeek v4 Flash</span>
            </div>
          </div>
        ))}
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
             onClick={() => setEditing(null)}>
          <div className="glass p-6 w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-[16px] font-semibold mb-4">配置设备 · {editing.name}</h3>

            <div className="space-y-4">
              <div>
                <label className="text-[11px] uppercase tracking-widest text-[var(--text-mute)] block mb-1">名称</label>
                <input className="input" value={name} onChange={e => setName(e.target.value)} />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-widest text-[var(--text-mute)] block mb-1">
                  个性配置 (JSON)
                  <span className="ml-2 text-[10px] text-[var(--text-mute)]">如 {"{\"style\":\"幽默\"}"}</span>
                </label>
                <textarea className="input h-24 resize-none font-mono" value={personality} onChange={e => setPersonality(e.target.value)} />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" onClick={() => saveAgent(editing)}>
                <i className="fas fa-floppy-disk"></i> 保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="mt-6 glass p-4 text-[12px] text-[var(--text-dim)] flex items-start gap-2">
        <i className="fas fa-circle-info text-[var(--indigo)] mt-0.5"></i>
        <div>
          所有设备共享<b>统一记忆库</b>和<b>统一 LLM 配置</b>（DeepSeek v4 Flash）。个性化通过 <span className="mono">personality</span> JSON 字段区分。设备注册通过 ESP32 连接时自动完成。
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AgentsPage });
