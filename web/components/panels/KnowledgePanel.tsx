"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import dynamic from "next/dynamic";
import { LoadingDots, Prose, SectionHeader, stripMarkdown, Tag, WhisperLine } from "@/components/ui";

// 菌丝 SVG 图较重且只在选中知识页后才需要 → 懒加载，/memory/ 首屏不为它付费
const WikiMyceliumGraph = dynamic(() => import("@/components/wiki-mycelium-graph"), {
  ssr: false,
  loading: () => (
    <div className="h-[340px] grid place-items-center text-sm text-[var(--text-weak)]">
      菌丝生长中…
    </div>
  ),
});
import { api } from "@/lib/api";
import { EASE } from "@/lib/motion";
import type { WikiPage as WikiPageType } from "@/lib/types";

/** 后端把数组存成 JSON 字符串；解析失败时按逗号/空白兜底 */
function parseStringArray(raw?: string): string[] {
  const s = (raw || "").trim();
  if (!s) return [];
  try {
    const v: unknown = JSON.parse(s);
    if (Array.isArray(v)) return v.map((x) => String(x).trim()).filter(Boolean);
    return [];
  } catch {
    return s.split(/[,，\s]+/).map((x) => x.trim()).filter(Boolean);
  }
}

/** 「记忆 · 知识」面板：原 /wiki/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function KnowledgePanel() {
  const [topics, setTopics] = useState<string[]>([]);
  const [pages, setPages] = useState<WikiPageType[]>([]);
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState(""); // 已生效的搜索词；空 = 标签云模式
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadTopics = useCallback(async () => {
    const res = await api.wiki();
    if (res === null) {
      setLoadError(true);
      return;
    }
    setLoadError(false);
    setTopics(res?.topics || []);
    setPages(res?.pages || []); // 空词时后端若回全部页，也一并展示
  }, []);

  useEffect(() => {
    loadTopics().finally(() => setLoading(false));
  }, [loadTopics]);

  const runSearch = useCallback(
    async (word: string) => {
      const w = word.trim();
      setQuery(w);
      setSelectedId(null);
      if (!w) {
        setTerm("");
        setSearching(true);
        await loadTopics();
        setSearching(false);
        return;
      }
      setTerm(w);
      setSearching(true);
      const res = await api.wiki(w);
      if (res === null) {
        setLoadError(true);
        setPages([]);
      } else {
        setLoadError(false);
        setPages(res?.pages || []);
      }
      setSearching(false);
    },
    [loadTopics]
  );

  /** 选中卡片后关系图在页面顶部展开，顺势滚回顶部 */
  const selectPage = useCallback((id: string | null) => {
    setSelectedId(id);
    if (id && typeof window !== "undefined") {
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    }
  }, []);

  const selected = useMemo(() => pages.find((p) => p.id === selectedId) || null, [pages, selectedId]);

  const linkedPages = useMemo(() => {
    if (!selected) return [];
    const seen = new Set<string>();
    const out: WikiPageType[] = [];
    for (const id of parseStringArray(selected.link_ids)) {
      if (seen.has(id)) continue;
      seen.add(id);
      const hit = pages.find((p) => p.id === id);
      if (hit) out.push(hit);
    }
    return out;
  }, [selected, pages]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingDots label="正在唤醒知识之林……" />
      </div>
    );
  }

  const showCloud = term === "" && topics.length > 0;
  const showWall = !searching && pages.length > 0;
  const showEmpty = !searching && !showCloud && pages.length === 0;

  return (
    <div className="space-y-12">
      <WhisperLine>实体之间，菌丝相连</WhisperLine>

      {/* 搜索 */}
      <form
        className="flex flex-col sm:flex-row gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(query);
        }}
      >
        <div className="flex-1">
          <input
            className="input-glow"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="寻找一个知识实体……"
            aria-label="搜索知识"
          />
        </div>
        <button type="submit" className="btn-lumen" disabled={searching}>
          {searching ? "寻找中…" : "寻找"}
        </button>
        {term && (
          <button type="button" className="btn-ghost" onClick={() => runSearch("")}>
            返回标签云
          </button>
        )}
      </form>

      {/* 菌丝关系图：选中一张卡后在页面顶部展开（数据驱动的进出场，保留 AnimatePresence） */}
      <AnimatePresence>
        {selected && (
          <motion.section
            key={selected.id}
            className="glass-card p-6"
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.6, ease: EASE.out }}
          >
            <div className="flex items-center justify-between gap-4 mb-4">
              <h2
                className="text-lg font-semibold"
                style={{ fontFamily: "var(--font-serif)", color: "var(--text-main)" }}
              >
                菌丝网络 · {selected.title}
              </h2>
              <div className="flex items-center gap-4">
                {linkedPages.length > 0 && (
                  <span
                    className="text-[11px]"
                    style={{ color: "var(--text-weak)", fontFamily: "var(--font-mono)" }}
                  >
                    {linkedPages.length} 条菌丝相连
                  </span>
                )}
                <button type="button" className="btn-ghost" onClick={() => setSelectedId(null)}>
                  收起
                </button>
              </div>
            </div>
            {linkedPages.length === 0 ? (
              <p
                className="serif py-8 text-center text-sm"
                style={{ color: "var(--text-weak)", letterSpacing: "0.06em" }}
              >
                这页知识还孤立着，等待菌丝蔓延
              </p>
            ) : (
              <WikiMyceliumGraph page={selected} linked={linkedPages} onSelect={selectPage} />
            )}
          </motion.section>
        )}
      </AnimatePresence>

      {/* 主题标签云：无搜索词时 */}
      {showCloud && (
        <section>
          <SectionHeader title="主题" subtitle="点击一个词，让菌丝为你带路" />
          <div className="flex flex-wrap gap-3">
            {topics.map((t, i) => (
              <motion.button
                key={t}
                type="button"
                className="cursor-pointer"
                aria-label={`搜索「${t}」`}
                initial={{ opacity: 0, y: 12 }}
                animate={{
                  opacity: 1,
                  y: 0,
                  transition: { delay: Math.min(i * 0.04, 0.8), duration: 0.6, ease: EASE.out },
                }}
                whileHover={{ y: -2, transition: { duration: 0.35, ease: EASE.out } }}
                onClick={() => runSearch(t)}
              >
                <Tag color="indigo">{t}</Tag>
              </motion.button>
            ))}
          </div>
        </section>
      )}

      {searching && <LoadingDots label="正在寻找相关的知识页……" />}

      {/* 实体卡片墙 */}
      {showWall && (
        <section>
          <SectionHeader
            title={term ? `「${term}」的知识页` : "全部知识页"}
            subtitle={term ? `${pages.length} 页与之相应` : "点击一张卡，看它的菌丝网络"}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 cv-auto">
            {pages.map((p, i) => {
              const tags = parseStringArray(p.tags);
              const isSelected = p.id === selectedId;
              return (
                <motion.article
                  key={p.id}
                  className="glass-card p-6 cursor-pointer"
                  style={isSelected ? { borderColor: "var(--edge-active)" } : undefined}
                  initial={{ opacity: 0, y: 28 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.05, 0.5), duration: 0.8, ease: EASE.out }}
                  onClick={() => selectPage(isSelected ? null : p.id)}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      selectPage(isSelected ? null : p.id);
                    }
                  }}
                >
                  <h3 className="text-base font-semibold mb-3" style={{ fontFamily: "var(--font-serif)" }}>
                    {p.title}
                  </h3>
                  {isSelected ? (
                    <div className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-dim)" }}>
                      <Prose text={p.body} />
                    </div>
                  ) : (
                    <p className="text-sm leading-relaxed mb-4 line-clamp-4" style={{ color: "var(--text-dim)" }}>
                      {stripMarkdown(p.body)}
                    </p>
                  )}
                  {tags.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-3">
                      {tags.map((t) => (
                        <Tag key={t} color="indigo">
                          {t}
                        </Tag>
                      ))}
                    </div>
                  )}
                  <div
                    className="text-[11px]"
                    style={{ color: "var(--text-weak)", fontFamily: "var(--font-mono)" }}
                  >
                    {(p.created_at || "").slice(0, 10)}
                  </div>
                </motion.article>
              );
            })}
          </div>
        </section>
      )}

      {showEmpty && (
        <EmptyState
          message={
            loadError
              ? "炉火熄了——连不上后端，知识菌丝暂停生长"
              : term
                ? "这束菌丝还没有连到任何知识页，换个词试试"
                : "知识之林尚未生长"
          }
        />
      )}
    </div>
  );
}
