"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import { LoadingDots, Tag, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import { localizeDisplayText } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { Recommendation } from "@/lib/types";

/** 推荐方向（局部映射：数据层英文键 → 中文） */
const KIND_LABELS: Record<string, string> = {
  book: "书籍",
  movie: "电影",
  action: "行动",
};
const KINDS = Object.keys(KIND_LABELS);

/** 「今天 · 推荐」面板：原 /recommend/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function RecommendPanel() {
  const [kind, setKind] = useState("book");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleSearch() {
    if (loading) return;
    setLoading(true);
    setFailed(false);
    setSearched(true);
    try {
      // 端点需要联网搜索 + LLM，可能很慢；失败时 post 包装返回 null
      const res = await api.recommend(kind, query.trim());
      if (res) {
        setResults(Array.isArray(res.recommendations) ? res.recommendations : []);
      } else {
        setResults([]);
        setFailed(true);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <WhisperLine>从你的记忆里，打捞下一件值得遇见的事物</WhisperLine>

      {/* 控制区：方向 chips + 查询输入（可空，空则由后端按画像推荐） */}
      <div className="mt-8 flex flex-col gap-4">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="推荐方向">
          {KINDS.map((k) => {
            const active = k === kind;
            return (
              <button
                key={k}
                role="tab"
                aria-selected={active}
                onClick={() => setKind(k)}
                className="px-4 py-2 rounded-full text-[13px] font-medium"
                style={{
                  background: active ? "var(--ind-16)" : "transparent",
                  color: active ? "var(--indigo-deep)" : "var(--text-dim)",
                  border: `1px solid ${active ? "var(--edge-active)" : "var(--edge)"}`,
                  boxShadow: active ? "0 0 12px var(--ind-10)" : "none",
                  transition: "all 0.5s var(--ease-out)",
                }}
              >
                {KIND_LABELS[k]}
              </button>
            );
          })}
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            className="input-glow flex-1"
            placeholder="想遇见什么？留空则按你的画像推荐……"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button className="btn-lumen" onClick={handleSearch} disabled={loading}>
            {loading ? "打捞中…" : "打捞"}
          </button>
        </div>
      </div>

      {/* 结果瀑布 */}
      <div className="mt-12">
        {loading ? (
          <div className="flex justify-center py-16">
            <LoadingDots label="正在为你打捞……" />
          </div>
        ) : failed ? (
          <EmptyState message="炉火熄了——推荐暂时没有回音，稍后再试" />
        ) : results.length === 0 ? (
          <EmptyState
            message={
              searched
                ? "此刻没有打捞到什么，换个方向试试"
                : "选一个方向，或写下一点心情，我来为你打捞"
            }
          />
        ) : (
          <div className="columns-1 md:columns-2 lg:columns-3 gap-5 space-y-5">
            {results.map((rec, i) => {
              const basedOn = Array.isArray(rec.based_on)
                ? rec.based_on.filter((b): b is string => typeof b === "string" && b.trim().length > 0)
                : [];
              return (
                <motion.article
                  key={`${rec.item}-${i}`}
                  className="glass-card p-6 break-inside-avoid"
                  initial={{ opacity: 0, y: 28 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.06, duration: 0.8, ease: EASE.out }}
                >
                  <h3
                    className="serif font-semibold text-xl"
                    style={{ lineHeight: 1.7, color: "var(--text-main)" }}
                  >
                    {rec.item}
                  </h3>
                  {typeof rec.reason === "string" && rec.reason && (
                    <p className="mt-3 text-sm" style={{ color: "var(--text-dim)", lineHeight: 1.8 }}>
                      {localizeDisplayText(rec.reason)}
                    </p>
                  )}
                  {basedOn.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {basedOn.map((b, j) => (
                        <Tag key={j} color="mineral">
                          {b}
                        </Tag>
                      ))}
                    </div>
                  )}
                </motion.article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
