"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import { LoadingDots, Prose, stripMarkdown, TypewriterText, WhisperLine } from "@/components/ui";
import { EvidenceEmbers } from "@/components/chat-evidence";
import { api } from "@/lib/api";
import { EASE } from "@/lib/motion";
import type { ChatLog } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  evidence: string[];
  createdAt: string;
  /** 发送失败的低语回显（余烬橙发丝边 + 弱化） */
  failed?: boolean;
  /** 历史批量入场时的交错延迟 */
  delay?: number;
}

const TIME_STYLE: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 10,
  letterSpacing: "0.08em",
  color: "var(--text-weak)",
};

function normalizeEvidence(ev: ChatLog["evidence"]): string[] {
  if (Array.isArray(ev)) return ev.filter((s): s is string => typeof s === "string" && s.trim().length > 0);
  if (typeof ev === "string" && ev.trim()) return [ev];
  return [];
}

/** 等宽时间：HH:mm，解析失败则从原串中捞时分 */
function emberTime(iso: string): string {
  const d = new Date(iso);
  if (!Number.isNaN(d.getTime())) {
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }
  const m = iso.match(/(\d{1,2}):(\d{2})/);
  return m ? `${m[1].padStart(2, "0")}:${m[2]}` : "";
}

let seq = 0;
function nextId(prefix: string): string {
  seq += 1;
  return `${prefix}-${Date.now()}-${seq}`;
}

/**
 * 「对话」面板：原 /chat/ 的全部内容，本目的地没有二级 tab。
 *
 * 视口高度：旧页写死 `calc(100vh-120px)`，那是按旧 PageTransition（标题渲染在
 * max-width 容器之外、无统一 padding）算的。新外壳里输入框上方叠了
 * .pa-page 的 30px 顶 padding + 标题块（约 88px），下方还有 .pa-page 的 96px
 * 底 padding（同时兜住底部 StatusStrip 的 14px），合计约 214px。这里取 220px
 * 留一点余量，保证输入框与提示行始终落在折叠线之上、不被 StatusStrip 压住。
 */
export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [histState, setHistState] = useState<"loading" | "ready" | "error">("loading");
  const [lastAssistantId, setLastAssistantId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback((instant = false) => {
    const el = scrollRef.current;
    if (!el) return;
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: instant || reduced ? "auto" : "smooth" });
  }, []);

  /* 载入过往的低语：后端按新→旧返回，倒序转为消息流 */
  useEffect(() => {
    let cancelled = false;
    api
      .chatLog("30")
      .then((res) => {
        if (cancelled) return;
        const logs = res?.chat_log ?? [];
        const msgs: Message[] = [...logs].reverse().map((m, i) => ({
          id: `hist-${String(m.id)}`,
          role: m.role === "assistant" ? "assistant" : "user",
          content: m.content ?? "",
          evidence: normalizeEvidence(m.evidence),
          createdAt: m.created_at ?? "",
          delay: Math.min(i * 0.03, 0.45),
        }));
        setMessages(msgs);
        setHistState("ready");
        requestAnimationFrame(() => scrollToBottom(true));
      })
      .catch(() => {
        if (!cancelled) setHistState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [scrollToBottom]);

  useEffect(() => {
    if (histState === "ready") scrollToBottom();
  }, [messages, sending, histState, scrollToBottom]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    const userMsg: Message = {
      id: nextId("u"),
      role: "user",
      content: text,
      evidence: [],
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const res = await api.chat(text, conversationId || undefined);
      const assistantMsg: Message = {
        id: nextId("a"),
        role: "assistant",
        content: res.reply ?? "",
        evidence: normalizeEvidence(res.evidence),
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setLastAssistantId(assistantMsg.id);
      if (res.conversation_id) setConversationId(res.conversation_id);
    } catch {
      /* 失败：回显低语，并把原文放回输入框 */
      setInput(text);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId("a"),
          role: "assistant" as const,
          content: "（炉火熄了——这条没送出去，稍后再试）",
          evidence: [],
          createdAt: new Date().toISOString(),
          failed: true,
        },
      ]);
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-220px)] min-h-[420px] w-full max-w-[860px] flex-col">
      <WhisperLine>炉火正温——说点什么，召回的余烬会悄悄融入回答</WhisperLine>

      {/* 消息流 */}
      <div
        ref={scrollRef}
        className="mt-4 min-h-0 flex-1 space-y-7 overflow-y-auto py-4 pr-2"
      >
        {histState === "loading" && (
          <div className="flex justify-center pt-[16vh]">
            <LoadingDots label="正在唤醒过往的低语……" />
          </div>
        )}
        {histState !== "loading" && messages.length === 0 && (
          <div className="pt-[12vh]">
            <EmptyState
              message={
                histState === "error"
                  ? "炉火熄了——读不到过往的低语"
                  : "沉睡的种子等待第一次低语"
              }
            />
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <MessageRow key={msg.id} msg={msg} typewrite={msg.id === lastAssistantId} />
          ))}
        </AnimatePresence>
        {sending && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE.out }}
            className="flex justify-start"
          >
            <div className="pl-5" style={{ borderLeft: "2px solid var(--ind-25)" }}>
              <LoadingDots label="炉边正在酝酿回答……" />
            </div>
          </motion.div>
        )}
      </div>

      {/* 低语输入 */}
      <div className="pb-8 pt-3">
        <div className="relative">
          <textarea
            ref={textareaRef}
            className="input-glow resize-none pr-16"
            rows={2}
            placeholder={sending ? "炉火正忙……" : "低语……"}
            value={input}
            disabled={sending}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void handleSend();
              }
            }}
            aria-label="输入想对菌林说的话"
          />
          <button
            type="button"
            className="btn-lumen absolute bottom-3.5 right-3.5 h-11 w-11 !rounded-xl !p-0"
            onClick={() => void handleSend()}
            disabled={!input.trim() || sending}
            aria-label="发送低语"
          >
            {sending ? (
              <span className="empty-seed-dot" style={{ width: 10, height: 10 }} />
            ) : (
              <svg
                width="17"
                height="17"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            )}
          </button>
        </div>
        <div
          className="mt-2.5 flex items-center justify-between px-1"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.08em",
            color: "var(--text-weak)",
          }}
        >
          <span>Enter 发送 · Shift+Enter 换行</span>
          {messages.length > 0 && (
            <span>
              {conversationId ? "炉火相续" : "新起一炉"} · {messages.length} 段低语
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageRow({ msg, typewrite }: { msg: Message; typewrite: boolean }) {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 18, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.7, ease: EASE.out, delay: msg.delay ?? 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      {isUser ? <UserBubble msg={msg} /> : <AssistantBubble msg={msg} typewrite={typewrite} />}
    </motion.div>
  );
}

/** 用户：靠右暖纸气泡（abyss-1 底 + lumen-10 发丝边） */
function UserBubble({ msg }: { msg: Message }) {
  return (
    <div
      className="max-w-[78%] px-5 py-3.5"
      style={{
        background: "linear-gradient(160deg, var(--porcelain-1), var(--porcelain-2))",
        border: "1px solid var(--ind-10)",
        borderRadius: "18px 18px 6px 18px",
      }}
    >
      <p
        className="whitespace-pre-wrap text-sm"
        style={{ lineHeight: 1.9, color: "var(--text-main)" }}
      >
        {msg.content}
      </p>
      <div className="mt-1.5 text-right" style={TIME_STYLE}>
        {emberTime(msg.createdAt)}
      </div>
    </div>
  );
}

/** 助手：靠左无边框，2px lumen 发丝边 + 衬线正文；最新一条逐字生长 */
function AssistantBubble({ msg, typewrite }: { msg: Message; typewrite: boolean }) {
  return (
    <div
      className="max-w-[84%] pl-5"
      style={{
        borderLeft: msg.failed ? "2px solid var(--ochre)" : "2px solid var(--indigo)",
        opacity: msg.failed ? 0.75 : 1,
      }}
    >
      {typewrite && !msg.failed ? (
        <p
          className="serif whitespace-pre-wrap"
          style={{
            fontSize: 15,
            lineHeight: 2,
            color: msg.failed ? "var(--text-weak)" : "var(--text-main)",
          }}
        >
          <TypewriterText text={stripMarkdown(msg.content)} speed={20} />
        </p>
      ) : (
        <Prose
          text={msg.content}
          className="serif"
          style={{
            fontSize: 15,
            lineHeight: 2,
            color: msg.failed ? "var(--text-weak)" : "var(--text-main)",
          }}
        />
      )}
      {msg.evidence.length > 0 && <EvidenceEmbers evidence={msg.evidence} />}
      <div className="mt-2" style={TIME_STYLE}>
        {emberTime(msg.createdAt)}
      </div>
    </div>
  );
}
