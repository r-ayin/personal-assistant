"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, Link2, LoaderCircle, WifiOff } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { ChatLog, LiveEvent } from "@/lib/types";

interface ConversationPanelProps {
  initialMessages: ChatLog[];
  connected: boolean;
  liveEvent: LiveEvent | null;
}

function evidenceList(value: ChatLog["evidence"]): string[] {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.map(String) : [value];
  } catch {
    return [value];
  }
}

export default function ConversationPanel({ initialMessages, connected, liveEvent }: ConversationPanelProps) {
  const [messages, setMessages] = useState<ChatLog[]>(initialMessages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const viewport = useRef<HTMLDivElement>(null);
  const seenLive = useRef(new Set<string>());

  useEffect(() => setMessages(initialMessages), [initialMessages]);

  useEffect(() => {
    if (!liveEvent || liveEvent.type !== "chat_reply") return;
    const data = liveEvent.data as { text?: string; evidence?: string[]; is_partial?: boolean };
    if (data.is_partial || !data.text) return;
    const signature = `${data.text}\u0000${(data.evidence || []).join("\u0000")}`;
    if (seenLive.current.has(signature)) return;
    seenLive.current.add(signature);
    setMessages((current) => [
      ...current,
      {
        id: signature,
        role: "assistant",
        content: data.text || "",
        evidence: data.evidence || [],
        created_at: liveEvent.ts,
      },
    ]);
  }, [liveEvent]);

  useEffect(() => {
    if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [messages, sending]);

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || sending || !connected) return;
    const now = new Date().toISOString();
    setSending(true);
    setError("");
    setMessages((current) => [
      ...current,
      { id: `local:${now}`, role: "user", content: text, created_at: now },
    ]);
    setDraft("");
    try {
      const response = conversationId
        ? await api.chat(text, conversationId)
        : await api.chat(text);
      const nextConversationId = response.conversation_id?.trim();
      if (nextConversationId) setConversationId(nextConversationId);
      const liveSignature = `${response.reply}\u0000${response.evidence.join("\u0000")}`;
      seenLive.current.add(liveSignature);
      setMessages((current) => [
        ...current,
        {
          id: `reply:${now}`,
          role: "assistant",
          content: response.reply,
          evidence: response.evidence,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (reason) {
      setDraft(text);
      setError(reason instanceof ApiError ? reason.message : "发送失败，请稍后重试");
    } finally {
      setSending(false);
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <section className="conversation" aria-label="对话">
      <header className="conversation-heading">
        <div>
          <p>今天</p>
          <h1>和 PA 说说现在要处理的事</h1>
        </div>
        <span className={connected ? "connection is-online" : "connection"}>
          {connected ? "实时连接" : "连接中断"}
        </span>
      </header>

      <div className="conversation-scroll" ref={viewport} aria-live="polite">
        {messages.length === 0 && (
          <div className="conversation-empty">
            <p>从一个具体问题开始。</p>
            <span>对话会保留依据，提醒与日程在右侧同步更新。</span>
          </div>
        )}
        {messages.map((message) => {
          const evidence = evidenceList(message.evidence);
          return (
            <article key={message.id} className={`message message-${message.role}`}>
              <div className="message-meta">
                <span>{message.role === "user" ? "你" : "PA"}</span>
                <time dateTime={message.created_at}>
                  {new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
                </time>
              </div>
              <p>{message.content}</p>
              {evidence.length > 0 && (
                <div className="evidence-list" aria-label="回复依据">
                  <Link2 size={13} aria-hidden="true" />
                  {evidence.map((item) => <span key={item}>{item}</span>)}
                </div>
              )}
            </article>
          );
        })}
        {sending && (
          <div className="message-pending">
            <LoaderCircle size={15} className="spin" aria-hidden="true" />
            PA 正在整理
          </div>
        )}
      </div>

      <form className="composer" onSubmit={sendMessage}>
        {!connected && (
          <div className="composer-alert" role="status">
            <WifiOff size={14} aria-hidden="true" />
            实时连接断开，输入内容会保留
          </div>
        )}
        <div className="composer-row">
          <textarea
            aria-label="消息"
            placeholder="输入消息"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onComposerKeyDown}
            rows={2}
          />
          <button type="submit" aria-label="发送消息" title="发送" disabled={!connected || sending || !draft.trim()}>
            {sending ? <LoaderCircle size={18} className="spin" /> : <ArrowUp size={18} />}
          </button>
        </div>
        {error && <p className="composer-error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
