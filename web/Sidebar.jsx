function Sidebar({ route, onNavigate }){
  const groups = [
    {
      label:"主视图",
      items:[
        { key:"dashboard", icon:"fa-grid-2", text:"仪表盘" },
        { key:"chat",      icon:"fa-comments", text:"对话" },
      ],
    },
    {
      label:"输入流",
      items:[
        { key:"inbox",     icon:"fa-inbox", text:"接入转录流", badge:3 },
        { key:"memories",  icon:"fa-brain", text:"记忆库" },
      ],
    },
    {
      label:"自动化",
      items:[
        { key:"calendar",  icon:"fa-calendar-days", text:"自动日历" },
        { key:"reminders", icon:"fa-bell", text:"定时提醒", badge:2 },
        { key:"recommend", icon:"fa-sparkles", text:"推荐引擎" },
      ],
    },
    {
      label:"知识 / 治理",
      items:[
        { key:"persona",   icon:"fa-user-astronaut", text:"数字分身" },
        { key:"wiki",      icon:"fa-book", text:"个人 wiki" },
        { key:"verify",    icon:"fa-shield-check", text:"反幻觉体检" },
      ],
    },
    {
      label:"系统",
      items:[
        { key:"settings",  icon:"fa-sliders", text:"设置 / LLM" },
      ],
    },
  ];

  return (
    <aside className="w-[244px] shrink-0 border-r border-[var(--border-soft)] bg-[var(--bg-elev)] flex flex-col">
      {/* Brand */}
      <div className="px-5 pt-5 pb-4 border-b border-[var(--border-soft)]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--indigo)] to-[#3FB68B] flex items-center justify-center text-white shadow-lg shadow-[rgba(91,141,239,0.25)]">
            <i className="fas fa-circle-dot" style={{fontSize:13}}></i>
          </div>
          <div>
            <div className="text-[14px] font-semibold tracking-tight">Persona·OS</div>
            <div className="text-[10px] text-[var(--text-mute)] uppercase tracking-[0.22em] mono">control plane</div>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2 text-[11px] text-[var(--text-dim)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--green)] animate-pulse"></span>
          <span className="mono">api.local · 184ms</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3">
        {groups.map(g => (
          <div key={g.label} className="px-3 mb-4">
            <div className="px-2 py-1.5 text-[10px] uppercase tracking-[0.22em] text-[var(--text-mute)]">{g.label}</div>
            <div className="space-y-1">
              {g.items.map(it => (
                <button
                  key={it.key}
                  onClick={()=>onNavigate(it.key)}
                  className={"nav-item w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] text-[var(--text-dim)] border border-transparent "+(route===it.key?"active":"")}
                >
                  <i className={"fas "+it.icon+" nav-icon w-4 text-center text-[13px]"}></i>
                  <span className="flex-1 text-left">{it.text}</span>
                  {it.badge && (
                    <span className="text-[10px] mono px-1.5 py-0.5 rounded-md bg-[var(--indigo-soft)] text-[var(--indigo)] border border-[rgba(91,141,239,0.3)]">{it.badge}</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-3 border-t border-[var(--border-soft)] flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#3FB68B] to-[var(--indigo)] flex items-center justify-center text-[11px] font-semibold text-white">SY</div>
        <div className="flex-1 min-w-0">
          <div className="text-[12px] text-[var(--text)] truncate">石云鹏</div>
          <div className="text-[10px] text-[var(--text-mute)] mono truncate">persona v7 · local</div>
        </div>
        <button className="text-[var(--text-mute)] hover:text-[var(--text)] transition">
          <i className="fas fa-arrow-up-right-from-square text-[11px]"></i>
        </button>
      </div>
    </aside>
  );
}

Object.assign(window, { Sidebar });
