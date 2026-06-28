function TweaksPanel(){
  const { useState, useEffect } = React;
  const defaults = (typeof TWEAK_DEFAULTS !== "undefined") ? TWEAK_DEFAULTS : {};
  const [accent,setAccent]   = useState(defaults.accent   || "indigo");
  const [density,setDensity] = useState(defaults.density  || "cozy");
  const [showSource,setShow] = useState(defaults.showSource || "on");
  const [open,setOpen]       = useState(true);

  useEffect(()=>{ document.body.dataset.accent = accent; },[accent]);
  useEffect(()=>{ document.body.dataset.density = density; },[density]);
  useEffect(()=>{ document.body.dataset.showSource = showSource; },[showSource]);

  if(!open){
    return (
      <button onClick={()=>setOpen(true)} className="tweaks-panel" style={{padding:10,width:"auto"}} title="打开 Tweaks">
        <i className="fas fa-sliders" style={{color:"var(--indigo)"}}></i>
      </button>
    );
  }

  const accentOpts = [
    {k:"indigo", c:"#5B8DEF"},
    {k:"violet", c:"#8B7BEF"},
    {k:"teal",   c:"#3FB6B0"},
    {k:"amber",  c:"#E0A458"},
  ];

  return (
    <div className="tweaks-panel">
      <h3>
        <i className="fas fa-sliders"></i> Tweaks
        <button className="ml-auto text-[var(--text-mute)] hover:text-[var(--text)]" onClick={()=>setOpen(false)} title="收起">
          <i className="fas fa-xmark"></i>
        </button>
      </h3>

      <div className="tweaks-row">
        <label>主色 accent</label>
        <div className="seg-btns">
          {accentOpts.map(o => (
            <button key={o.k} onClick={()=>setAccent(o.k)} className={"seg-btn "+(accent===o.k?"active":"")}>
              <span style={{display:"inline-block",width:8,height:8,borderRadius:99,background:o.c,marginRight:4,verticalAlign:"middle"}}></span>
              {o.k}
            </button>
          ))}
        </div>
      </div>

      <div className="tweaks-row">
        <label>密度 density</label>
        <div className="seg-btns">
          {["compact","cozy","comfy"].map(d=>(
            <button key={d} onClick={()=>setDensity(d)} className={"seg-btn "+(density===d?"active":"")}>{d}</button>
          ))}
        </div>
      </div>

      <div className="tweaks-row">
        <label>溯源 chip source</label>
        <div className="seg-btns">
          {["on","minimal","off"].map(d=>(
            <button key={d} onClick={()=>setShow(d)} className={"seg-btn "+(showSource===d?"active":"")}>{d}</button>
          ))}
        </div>
      </div>

      <div className="text-[10px] text-[var(--text-mute)] mono mt-3 leading-relaxed">
        本面板只控全局视觉变量，不动数据。
      </div>
    </div>
  );
}

Object.assign(window, { TweaksPanel });
