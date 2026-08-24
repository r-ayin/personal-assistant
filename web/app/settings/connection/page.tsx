"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { ApiError, api, clearApiToken, getApiToken, setApiToken } from "@/lib/api";

export default function ConnectionPage() {
  const [token, setToken] = useState("");
  const [stored, setStored] = useState(false);
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const value = getApiToken();
    setStored(Boolean(value));
  }, []);

  const verify = async (saveFirst: boolean) => {
    const submitted = token.trim();
    if (saveFirst) {
      if (!submitted) { setError("请输入 PA API Token。"); return; }
      setApiToken(submitted);
    }
    setChecking(true); setError(""); setMessage("");
    try {
      await api.health();
      await api.assistantPersonality();
      setStored(Boolean(getApiToken()));
      setMessage("连接与鉴权均正常");
      if (saveFirst) setToken("");
    } catch (reason) {
      if (reason instanceof ApiError && (reason.status === 401 || reason.status === 403)) {
        if (saveFirst) clearApiToken();
        setStored(Boolean(getApiToken()));
        setError("Token 无效或已过期，请检查后重新保存。");
      } else {
        setError(reason instanceof ApiError ? `无法连接 PA 后端：${reason.message}` : "无法连接 PA 后端。");
      }
    } finally { setChecking(false); }
  };

  const clear = () => {
    clearApiToken(); setToken(""); setStored(false); setMessage(""); setError("");
  };

  return (
    <div className="settings-page connection-page">
      <header className="settings-header"><div><p>SETTINGS / CONNECTION</p><h1>隐私与连接</h1><span>管理当前浏览器标签页访问 PA 后端所需的鉴权 Token。</span></div></header>
      {error && <div role="alert" className="settings-alert is-error"><AlertTriangle size={16} />{error}</div>}
      {message && <div role="status" className="settings-alert is-success"><CheckCircle2 size={16} />{message}</div>}

      <section className="settings-section connection-token">
        <div className="section-title"><div><h2>PA API Token</h2><p>Bearer Token 用于访问性格、画像、模型和弹幕等受保护接口。</p></div><KeyRound size={18} /></div>
        <label className="control-field"><span>PA API Token</span><input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} placeholder={stored ? "已保存于当前标签会话，输入新值可覆盖" : "输入 Token"} /></label>
        <div className="settings-actions align-left">
          <button className="control-button is-primary" onClick={() => void verify(true)} disabled={checking || !token.trim()}><ShieldCheck size={15} />{checking ? "验证中…" : "保存并验证"}</button>
          <button className="control-button" onClick={() => void verify(false)} disabled={checking || !stored}><CheckCircle2 size={15} />验证连接</button>
          <button className="control-button is-danger" onClick={clear} disabled={checking || !stored}><Trash2 size={15} />清除 Token</button>
        </div>
      </section>

      <section className="privacy-notice" aria-label="Token 存储说明">
        <ShieldCheck size={19} />
        <div><h2>仅当前标签会话</h2><p>Token 只保存在浏览器 sessionStorage，关闭当前标签页后由浏览器清理。它不会写入服务器、应用日志、localStorage 或持久磁盘。</p></div>
      </section>
    </div>
  );
}
