function SettingsPage(){
  const { useState, useEffect } = React;
  const m = window.MockData;

  const backends = [
    { k:"stub",            t:"stub",            desc:"开发桩，零依赖" },
    { k:"deepseek",        t:"deepseek",        desc:"DeepSeek API（默认 deepseek-v4-flash）" },
    { k:"anthropic_proxy", t:"anthropic_proxy", desc:"反代到 Claude 官方" },
    { k:"openai_compat",   t:"openai_compat",   desc:"OpenAI 兼容端点（含 GLM /api/paas/v4）" },
    { k:"glm_anthropic",   t:"glm_anthropic",   desc:"GLM 的 Anthropic 兼容端点（含 budget_tokens）" },
    { k:"ollama",          t:"ollama",          desc:"本地推理 (llama.cpp / gguf)" },
  ];

  const [backend,setBackend]   = useState("deepseek");
  const [model,setModel]       = useState("glm-4.6");
  const [baseUrl,setBaseUrl]   = useState("https://open.bigmodel.cn/api/paas/v4");
  const [apiKey,setApiKey]     = useState("");
  const [ctxWindow,setCtxWin]  = useState(200000);
  const [maxTokens,setMaxTok]  = useState(8192);
  const [effort,setEffort]     = useState("medium");
  const [saved,setSaved]       = useState(false);
  const [keyMask,setKeyMask]   = useState("未设置");
  const [saving,setSaving]     = useState(false);

  // 拉生效配置（key 掩码回显，不回填明文）
  useEffect(()=>{
    (async ()=>{
      const c = await window.PA.get("/settings/llm");
      if(!c || c.backend==="stub") return;
      c.backend && setBackend(c.backend);
      c.model && setModel(c.model);
      c.base_url && setBaseUrl(c.base_url);
      c.max_tokens && setMaxTok(c.max_tokens);
      c.thinking_effort && setEffort(c.thinking_effort);
      c.api_key_masked && setKeyMask(c.api_key_masked);
    })();
  },[]);

  const effects = {
    off:    { label:"off · 关闭",    color:"#94A0B4" },
    low:    { label:"低 · low",      color:"#5B8DEF" },
    medium: { label:"中 · medium",   color:"#E0A458" },
    high:   { label:"高 · high",     color:"#E0584F" },
  };

  // dynamic hint + native preview per backend × effort
  const hint = (()=>{
    if(backend==="openai_compat" && model.startsWith("glm") && effort!=="off"){
      return "⚠ GLM 的 OpenAI 兼容端点只支持开/关两档；低/中/高 在此后端下会塌缩为「开」。要按 budget 分档，请切到 glm_anthropic 后端。";
    }
    if(backend==="glm_anthropic"){
      return "✓ 按 budget_tokens 区分（min 1024，且 < max_tokens）。";
    }
    if(backend==="anthropic_proxy"){
      return "✓ Anthropic 原生 thinking.budget_tokens；Opus4.7+ 推荐 adaptive。";
    }
    if(backend==="ollama"){
      return "ⓘ 本地推理通常无原生 thinking 字段，档位仅影响系统提示中的「请展示思考过程」。";
    }
    if(model.startsWith("o") || model.startsWith("gpt-5")){
      return "✓ OpenAI 原生 reasoning_effort：o 系仅 low/medium/high；GPT-5 另支持 none/minimal/xhigh。";
    }
    if(model.startsWith("qwen")){
      return "✓ Qwen3：enable_thinking + thinking_budget（extra_body）。";
    }
    return "ⓘ 思考程度档位由后端映射为对应 provider 原生字段。";
  })();

  const nativePreview = (()=>{
    if(effort==="off"){
      if(backend==="openai_compat" && model.startsWith("glm")) return `{ "thinking": { "type": "disabled" } }`;
      if(model.startsWith("qwen")) return `{ "enable_thinking": false }`;
      return "// 省略 thinking 字段";
    }
    const budget = { low:4096, medium:12288, high:24576 }[effort];
    if(backend==="glm_anthropic" || backend==="anthropic_proxy") return `{ "thinking": { "type": "enabled", "budget_tokens": ${budget} } }`;
    if(backend==="openai_compat" && model.startsWith("glm")) return `{ "thinking": { "type": "enabled" } }   // GLM openai_compat 无 budget`;
    if(model.startsWith("o") || model.startsWith("gpt-5")) return `{ "reasoning_effort": "${effort}" }`;
    if(model.startsWith("qwen")) return `{ "enable_thinking": true, "thinking_budget": ${budget} }`;
    return `{ "thinking": { "type": "enabled" } }`;
  })();

  const displayKey = apiKey ? (apiKey.slice(0,4)+"…"+apiKey.slice(-4)) : keyMask;

  // thinking_format 按后端推导（与 llm.py 默认一致）
  const fmtFor = (be, mdl) => {
    if(be==="anthropic_proxy" || be==="glm_anthropic") return "anthropic";
    if(be==="openai_compat" && (mdl.startsWith("o")||mdl.startsWith("gpt-5"))) return "openai";
    if(be==="openai_compat" && mdl.startsWith("qwen")) return "qwen";
    return "glm";
  };

  const save = async ()=>{
    setSaving(true);
    const body = {
      backend, model, base_url: baseUrl, max_tokens: +maxTokens,
      thinking_effort: effort, thinking_format: fmtFor(backend, model),
      context_window: +ctxWindow,
    };
    if(apiKey) body.api_key = apiKey;          // 仅当用户输入新 key 才覆盖
    const r = await window.PA.post("/settings/llm", body);
    setSaving(false);
    if(r && r.effective){
      setSaved(true); setTimeout(()=>setSaved(false), 1800);
      if(r.effective.api_key_masked) setKeyMask(r.effective.api_key_masked);
      setApiKey("");                            // 清明文，避免残留
    }
  };

  return (
    <div className="p-8 max-w-[1320px] mx-auto">
      <window.SectionHeader
        subtitle="settings · /settings/llm"
        title="LLM 可插拔配置"
        icon="fa-sliders"
        right={<>
          <window.Tag color="green"><i className="fas fa-lock mr-1"></i>本地写入</window.Tag>
          <span className="text-[12px] text-[var(--text-dim)]">与 <span className="mono">cli llm</span> 同源</span>
        </>}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Current effective */}
        <div className="xl:col-span-1">
          <div className="glass p-5">
            <div className="flex items-center gap-2 mb-4">
              <i className="fas fa-circle-check text-[var(--green)]"></i>
              <div className="text-[14px] font-semibold">当前生效</div>
              <window.Tag color="green">READ ONLY</window.Tag>
            </div>
            <div className="space-y-3 text-[12.5px]">
              <Row k="backend"        v={backend} mono/>
              <Row k="model"          v={model} mono/>
              <Row k="base_url"       v={baseUrl} mono small/>
              <Row k="api_key"        v={displayKey} mono mask/>
              <Row k="context_window" v={ctxWindow.toLocaleString()+" tok"} mono/>
              <Row k="max_tokens"     v={maxTokens.toLocaleString()+" tok"} mono/>
              <Row k="thinking"       v={effects[effort].label} mono color={effects[effort].color}/>
            </div>

            <div className="mt-5 pt-4 border-t border-[var(--border-soft)]">
              <div className="text-[10.5px] uppercase tracking-widest text-[var(--text-mute)] mb-2">native preview</div>
              <pre className="mono text-[11.5px] bg-[var(--bg)] p-3 rounded-md border border-[var(--border-soft)] text-[var(--green)] whitespace-pre-wrap leading-5">{nativePreview}</pre>
            </div>
          </div>
        </div>

        {/* Edit form */}
        <div className="xl:col-span-2 space-y-6">
          {/* Backend switch */}
          <div className="glass p-5">
            <div className="text-[14px] font-semibold mb-1">后端切换 · PA_LLM_BACKEND</div>
            <div className="text-[12px] text-[var(--text-dim)] mb-4">选择 provider 适配层。切换后会重置一些字段默认值。</div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {backends.map(b=>(
                <button key={b.k} onClick={()=>setBackend(b.k)} className={"text-left p-3 rounded-lg border transition "+(backend===b.k?"border-[var(--indigo)] bg-[var(--indigo-soft)]":"border-[var(--border-soft)] hover:border-[#33415A] bg-[var(--bg-elev-2)]")}>
                  <div className="flex items-center justify-between">
                    <div className="text-[13px] font-semibold text-[var(--text)] mono">{b.t}</div>
                    {backend===b.k && <i className="fas fa-circle-check text-[var(--indigo)]"></i>}
                  </div>
                  <div className="text-[11px] text-[var(--text-dim)] mt-1 leading-5">{b.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Global override */}
          <div className="glass p-5">
            <div className="text-[14px] font-semibold mb-1">全局覆盖</div>
            <div className="text-[12px] text-[var(--text-dim)] mb-4">运行态覆盖层 → <span className="mono">config/default.json</span> → env，三段式合并；写入后立即生效。</div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="model" hint="例如 glm-4.6 / o3 / qwen3-32b / claude-opus-4-7">
                <input className="input mono" value={model} onChange={e=>setModel(e.target.value)} />
              </Field>
              <Field label="base_url" hint="provider endpoint">
                <input className="input mono" value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} />
              </Field>
              <Field label="context_window (token)">
                <input type="number" className="input mono" value={ctxWindow} onChange={e=>setCtxWin(+e.target.value)} />
              </Field>
              <Field label="max_tokens (token)" hint="须 > thinking budget；streaming 推荐 > 21333">
                <input type="number" className="input mono" value={maxTokens} onChange={e=>setMaxTok(+e.target.value)} />
              </Field>
              <Field label="api_key" hint="掩码回显，永不明文">
                <input type="password" className="input mono" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="sk-…" />
              </Field>
              <Field label="thinking_effort">
                <div className="seg-btns">
                  {["off","low","medium","high"].map(k=>(
                    <button key={k} onClick={()=>setEffort(k)} className={"seg-btn "+(effort===k?"active":"")}>
                      {k}
                    </button>
                  ))}
                </div>
              </Field>
            </div>

            {/* Dynamic hint */}
            <div className={"mt-4 p-3 rounded-lg border text-[12px] leading-5 "+(hint.startsWith("⚠")?"border-[rgba(224,164,88,0.4)] bg-[var(--gold-soft)] text-[var(--gold)]":"border-[rgba(63,182,139,0.3)] bg-[var(--green-soft)] text-[var(--green)]")}>
              {hint}
            </div>

            <div className="mt-5 flex items-center justify-between">
              <div className="text-[11px] text-[var(--text-mute)]">改动会同步给 <span className="mono">cli llm</span>，确保「前端改 = CLI 看 = 生效」。</div>
              <div className="flex items-center gap-2">
                <button className="btn btn-ghost" onClick={()=>{setBackend("deepseek");setModel("deepseek-v4-flash");setBaseUrl("https://api.deepseek.com/v1");setCtxWin(200000);setMaxTok(8192);setEffort("off");setApiKey("");}}>重置</button>
                <button className={"btn btn-primary "+(saving?"opacity-70":"")} onClick={save} disabled={saving}>
                  <i className={"fas "+(saving?"fa-spinner fa-spin":(saved?"fa-circle-check":"fa-floppy-disk"))}></i>
                  {saving?"保存中…":(saved?"已保存":"保存配置")}
                </button>
              </div>
            </div>
          </div>

          {/* Backend status preview */}
          <div className="glass p-5">
            <div className="text-[14px] font-semibold mb-3">运行依据 · 引用自官方文档</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[12px]">
              {[
                { p:"GLM (智谱)", f:"openai: thinking.type；anthropic: budget_tokens", limit:"openai 仅开/关；anthropic min 1024" },
                { p:"OpenAI o 系", f:"reasoning_effort (low/medium/high)", limit:"无 budget；推理 token 计入输出" },
                { p:"Qwen3 (百炼)", f:"enable_thinking + thinking_budget", limit:"thinking_budget=0 自适应" },
                { p:"Anthropic Claude", f:"thinking.{type, budget_tokens}", limit:"Opus4.7+ 推荐 adaptive" },
              ].map(r=>(
                <div key={r.p} className="p-3 rounded-md bg-[var(--bg-elev-2)] border border-[var(--border-soft)]">
                  <div className="text-[12.5px] font-semibold text-[var(--text)]">{r.p}</div>
                  <div className="mt-1 text-[11.5px] text-[var(--text-dim)] mono">{r.f}</div>
                  <div className="mt-1 text-[11px] text-[var(--text-mute)]">{r.limit}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v, mono, mask, color, small }){
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--text-mute)] text-[11px] uppercase tracking-widest">{k}</span>
      <span className={(mono?"mono ":"")+(small?"text-[11px] ":"text-[12.5px] ")+"text-right truncate max-w-[60%]"} style={color?{color}:{}}>
        {mask && <i className="fas fa-lock text-[10px] mr-1 text-[var(--text-mute)]"></i>}
        {v}
      </span>
    </div>
  );
}

function Field({ label, hint, children }){
  return (
    <div>
      <label className="text-[11px] uppercase tracking-widest text-[var(--text-mute)] mb-1.5 block">{label}</label>
      {children}
      {hint && <div className="mt-1 text-[10.5px] text-[var(--text-mute)]">{hint}</div>}
    </div>
  );
}

Object.assign(window, { SettingsPage });
