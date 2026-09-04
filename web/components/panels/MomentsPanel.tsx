"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import Reveal from "@/components/Reveal";
import ScrollReveal from "@/components/ScrollReveal";
import { LoadingDots, SectionHeader, SeedCard, Tag, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import { chatKindLabel, memoryKindLabel, momentTagLabel } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { Memory, Moment, RecallResponse } from "@/lib/types";

/** 召回策略的局部中文映射（lib/labels.ts 暂未覆盖，未命中键原样回退） */
const STRATEGY_LABELS: Record<string, string> = {
  hybrid: "混合召回",
  vector: "向量召回",
  fts: "全文检索",
  keyword: "关键词召回",
  bm25: "关键词召回",
  fallback: "兜底召回",
};

function strategyLabel(strategy?: string): string {
  const k = (strategy || "").trim();
  return STRATEGY_LABELS[k] || STRATEGY_LABELS[k.toLowerCase()] || k;
}

/** 对话对象：单聊「对她」、群聊「在某某群」，后接中文场景（如「对她 · 单聊」） */
function counterpartText(m: Moment): string {
  const p = (m.counterpart || "").trim();
  if (!p) return chatKindLabel(m.chat_kind) || "";
  const head = m.chat_kind === "group" ? `在${p}` : `对${p}`;
  const kind = chatKindLabel(m.chat_kind);
  return kind ? `${head} · ${kind}` : head;
}

function momentDate(m: Moment): string {
  return (m.timestamp || m.created_at || "").slice(0, 10);
}

/** 「记忆 · 时刻」面板：原 /memories/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function MomentsPanel() {
  const [moments, setMoments] = useState<Moment[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [query, setQuery] = useState("");
  const [recalling, setRecalling] = useState(false);
  const [recalled, setRecalled] = useState(false);
  const [recallRes, setRecallRes] = useState<RecallResponse | null>(null);
  const [recallError, setRecallError] = useState(false);

  useEffect(() => {
    Promise.all([api.moments(), api.memories()])
      .then(([mo, me]) => {
        if (mo === null && me === null) setLoadError(true);
        setMoments(mo?.moments || []);
        setMemories(me?.memories || []);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  const runRecall = useCallback(async () => {
    const q = query.trim();
    if (!q || recalling) return;
    setRecalling(true);
    setRecalled(true);
    setRecallError(false);
    try {
      const res = await api.recall(q, "8");
      setRecallRes(res);
    } catch {
      setRecallRes(null);
      setRecallError(true);
    } finally {
      setRecalling(false);
    }
  }, [query, recalling]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingDots label="正在唤醒菌林……" />
      </div>
    );
  }

  const maxScore = recallRes ? Math.max(...recallRes.items.map((it) => it.score), 0.000001) : 1;

  return (
    <div className="space-y-16">
      <WhisperLine>记忆不是数据库，是一座活着的菌林</WhisperLine>

      {/* 召回搜索 —— 向菌林低语一句话，混合召回最相关的记忆 */}
      <ScrollReveal as="section" y={36}>
        <SectionHeader title="召回" subtitle="向菌林低语一句话，混合召回最相关的记忆" />
        <form
          className="flex flex-col sm:flex-row gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            runRecall();
          }}
        >
          <div className="flex-1">
            <input
              className="input-glow"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="想找回哪段记忆？"
              aria-label="召回搜索"
            />
          </div>
          <button type="submit" className="btn-lumen" disabled={recalling || !query.trim()}>
            {recalling ? "召回中…" : "召回"}
          </button>
        </form>

        <div className="mt-6">
          {recalling && <LoadingDots label="正在召回记忆……" />}
          {!recalling && recallError && (
            <EmptyState message="炉火熄了——这次召回没有抵达，稍后再试" />
          )}
          {!recalling && !recallError && recalled && recallRes && recallRes.items.length === 0 && (
            <EmptyState message="菌林里还没有与这句话相应的记忆" />
          )}
          {!recalling && !recallError && recallRes && recallRes.items.length > 0 && (
            <>
              <p
                className="text-xs mb-3"
                style={{ color: "var(--text-weak)", fontFamily: "var(--font-mono)" }}
              >
                {recallRes.items.length} 条回响 · {recallRes.elapsed_ms}ms · {strategyLabel(recallRes.strategy)}
                {recallRes.truncated ? " · 已截断" : ""}
              </p>
              <div className="glass-card px-6 py-2">
                {recallRes.items.map((item, i) => (
                  <motion.div
                    key={item.id || i}
                    className="py-4"
                    style={{ borderTop: i === 0 ? "none" : "1px solid var(--edge)" }}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06, duration: 0.7, ease: EASE.out }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Tag color="indigo">{memoryKindLabel(item.kind)}</Tag>
                      <span
                        className="text-[11px]"
                        style={{ color: "var(--text-weak)", fontFamily: "var(--font-mono)" }}
                      >
                        相关度 {item.score.toFixed(2)}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-main)" }}>
                      {item.content}
                    </p>
                    {/* score 微光条：宽度 = score / 本批最高分 */}
                    <div
                      className="mt-3 h-[3px] rounded-full overflow-hidden"
                      style={{ background: "var(--ind-08)" }}
                    >
                      <motion.div
                        className="h-full rounded-full"
                        style={{ background: "linear-gradient(90deg, var(--ind-25), var(--indigo))" }}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.max(4, Math.round((item.score / maxScore) * 100))}%` }}
                        transition={{ delay: 0.2 + i * 0.06, duration: 0.9, ease: EASE.out }}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </>
          )}
        </div>
      </ScrollReveal>

      {/* 时刻种子墙 —— 一页页晒暖的信纸，各自 3~8s 相位呼吸 */}
      <ScrollReveal as="section" y={36} delay={0.06}>
        <SectionHeader title="时刻" subtitle="一页页晒暖的信纸，各自安静地呼吸" />
        {moments.length === 0 ? (
          <EmptyState
            message={loadError ? "炉火熄了——连不上后端，时刻们还在原地" : "菌林还在沉睡，等待第一颗种子"}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 cv-auto">
            {moments.map((m, i) => (
              <SeedCard
                key={m.id}
                quote={m.verbatim_quote}
                narrative={m.narrative}
                delay={Math.min(i * 0.06, 0.6)}
                meta={
                  <>
                    {(m.tags || []).map((t) => (
                      <Tag key={t} color="cinnabar">
                        {momentTagLabel(t)}
                      </Tag>
                    ))}
                    {counterpartText(m) && <span>{counterpartText(m)}</span>}
                    {momentDate(m) && <span>{momentDate(m)}</span>}
                  </>
                }
              />
            ))}
          </div>
        )}
      </ScrollReveal>

      {/* 知识记忆 —— 从话语里沉淀下来的事实、技能与偏好 */}
      <ScrollReveal as="section" y={36} delay={0.12}>
        <SectionHeader title="知识记忆" subtitle="从话语里沉淀下来的事实、技能与偏好" />
        {memories.length === 0 ? (
          <EmptyState message={loadError ? "炉火熄了——连不上后端" : "知识菌丝还在生长中"} />
        ) : (
          <Reveal className="glass-card px-6 py-2">
            {memories.map((m, i) => (
              <motion.div
                key={m.id}
                className="py-4"
                style={{ borderTop: i === 0 ? "none" : "1px solid var(--edge)" }}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.04, 0.5), duration: 0.7, ease: EASE.out }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Tag color="mineral">{memoryKindLabel(m.kind)}</Tag>
                  <span
                    className="text-[11px]"
                    style={{ color: "var(--text-weak)", fontFamily: "var(--font-mono)" }}
                  >
                    {(m.created_at || "").slice(0, 10)}
                  </span>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-main)" }}>
                  {m.content}
                </p>
              </motion.div>
            ))}
          </Reveal>
        )}
      </ScrollReveal>
    </div>
  );
}
