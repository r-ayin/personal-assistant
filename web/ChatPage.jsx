function ChatPage(){
  const { useState, useRef, useEffect } = React;
  const m = window.MockData;
  const [logs,setLogs] = useState(m.chatLog);
  const [draft,setDraft] = useState("");
  const [sending,setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(()=>{
    if(scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  },[logs,sending]);

  const send = async () => {
    if(!draft.trim() || sending) return;
    const text = draft.trim();
    const now = new Date().toISOString().replace("T"," ").slice(0,19);
    const userMsg = { id: Date.now(), role:"user", content: text, created_at: now };
    setLogs(l=>[...l, userMsg]);
    setDraft("");
    setSending(true);
    const r = await window.PA.post("/chat", { message: text });
    const reply = {
      id: Date.now()+1, role:"assistant",
      content: (r && r.reply) || "（无回复：后端不可达，回落 mock）",
      created_at: new Date().toISOString().replace("T"," ").slice(0,19),
      evidence: (r && r.evidence) || [],
    };
    setLogs(l=>[...l, reply]);
    setSending(false);
  };

  const doClear = async () => {
    await window.PA.post("/chat/clear");
    const j = await window.PA.get("/chat-log");
    if (j && j.logs) window.PA.updateMock("chatLog", j.logs);
    setLogs([]);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-8 pt-8 max-w-[1100px] w-full mx-auto">
        <window.SectionHeader
          subtitle="chat · /chat"
          title="与你的助手对话"
          icon="fa-comments"
          right={<>
            <window.Tag>connected: GLM-4.6</window.Tag>
            <button className="btn btn-ghost" onClick={doClear}><i className="fas fa-eraser"></i> 清空</button>
          </>}
        />
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-8">
        <div className="max-w-[1100px] mx-auto space-y-5 pb-6">
          {logs.map(msg=>(
            <Bubble key={msg.id} msg={msg} />
          ))}
          {sending && (
            <div className="flex items-end gap-3">
              <Avatar role="assistant" />
              <div className="glass px-4 py-3 rounded-2xl rounded-bl-sm">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[var(--text-mute)] animate-bounce" style={{animationDelay:"0ms"}}></span>
                  <span className="w-2 h-2 rounded-full bg-[var(--text-mute)] animate-bounce" style={{animationDelay:"120ms"}}></span>
                  <span className="w-2 h-2 rounded-full bg-[var(--text-mute)] animate-bounce" style={{animationDelay:"240ms"}}></span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* composer */}
      <div className="border-t border-[var(--border-soft)] bg-[var(--bg-elev)] px-8 py-4">
        <div className="max-w-[1100px] mx-auto">
          <div className="flex items-end gap-3">
            <button className="btn btn-ghost h-9 w-9 p-0 justify-center"><i className="fas fa-paperclip"></i></button>
            <div className="flex-1 relative">
              <textarea
                rows={1}
                className="input resize-none min-h-[40px] max-h-32 pr-12"
                placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"
                value={draft}
                onChange={e=>setDraft(e.target.value)}
                onKeyDown={e=>{ if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); send();} }}
              />
              <span className="absolute right-3 bottom-2 text-[10px] text-[var(--text-mute)] mono">{draft.length}</span>
            </div>
            <button className={"btn btn-primary h-9 "+(sending?"opacity-70":"")} onClick={send} disabled={sending}>
              <i className="fas fa-paper-plane"></i> 发送
            </button>
          </div>
          <div className="mt-2 text-[10.5px] text-[var(--text-mute)] flex items-center gap-3">
            <span><i className="fas fa-shield-halved mr-1"></i>本地优先：key 永不出现在前端；原始数据不持久化。</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Avatar({ role }){
  const isUser = role==="user";
  return (
    <div className={"w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 "+(isUser?"bg-gradient-to-br from-[#3FB68B] to-[var(--indigo)] text-white":"bg-[var(--bg-elev-2)] text-[var(--indigo)] border border-[var(--border)]")}>
      {isUser ? "SY" : <i className="fas fa-circle-dot"></i>}
    </div>
  );
}

function Bubble({ msg }){
  const isUser = msg.role==="user";
  return (
    <div className={"flex items-end gap-3 "+(isUser?"flex-row-reverse":"")}>
      <Avatar role={msg.role} />
      <div className={"max-w-[78%] "+(isUser?"items-end":"items-start")+" flex flex-col gap-1.5"}>
        <div className={"px-4 py-3 rounded-2xl text-[14px] leading-6 "+(isUser
          ? "bg-[var(--indigo)] text-white rounded-br-sm"
          : "glass rounded-bl-sm text-[var(--text)]")}>
          {msg.content}
        </div>
        <div className={"flex items-center gap-2 flex-wrap "+(isUser?"justify-end":"")}>
          <window.TimeChip created_at={msg.created_at} time_kind="received" compact />
          {!isUser && msg.evidence && msg.evidence.map(e=>(
            <window.SourceChip key={e} type={e.startsWith("wiki")?"wiki":"memory"} id={e} label={e}/>
          ))}
          {!isUser && msg.evidence && <window.GenerativeBadge />}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ChatPage });
