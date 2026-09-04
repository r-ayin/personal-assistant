"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { HonestEmpty, useAsync } from "@/components/portrait-bits";
import { SectionHeader } from "@/components/ui";

/**
 * 检索 tab：混合检索（FTS5 bigram + 向量网关 + RRF + GA 三维终排）。
 * 向量网关不在线时后端自动降级为纯 FTS，sources 里会标明命中来自哪路。
 * 空结果就是空结果，不编示例。
 */
export default function MemorySearchPanel() {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);
  const { loading, error, data } = useAsync(
    () => (submitted ? api.memorySearch(submitted, "20") : Promise.resolve(null)),
    [submitted],
  );

  return (
    <div className="space-y-8">
      <form
        className="flex gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const v = q.trim();
          if (v) setSubmitted(v);
        }}
      >
        <input
          className="input-glow"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜你说过的话、时刻、转写…"
          aria-label="记忆检索"
        />
        <button type="submit" className="btn-lumen shrink-0">检索</button>
      </form>

      {!submitted && (
        <HonestEmpty title="输入关键词，在你自己的 72 万条消息里找" />
      )}
      {submitted && loading && <HonestEmpty title="检索中…" />}
      {submitted && error && <HonestEmpty title="连不上后端" hint={error} />}
      {submitted && data && (
        <section>
          <SectionHeader
            title={`「${submitted}」`}
            subtitle={`${data.results.length} 条命中 · sources 标明命中来自 fts / vec`}
          />
          {data.results.length === 0 ? (
            <HonestEmpty title="没有命中" hint="换个词，或确认 FTS 索引已建（memcore.retrieve index）" />
          ) : (
            <div className="space-y-4 cv-auto">
              {data.results.map((r) => (
                <article key={r.id} className="glass-card p-5">
                  <p className="text-[13.5px] leading-relaxed text-[var(--ink-900)]">{r.text}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[11px] text-[var(--text-weak)]">
                    <span>{r.ts.slice(0, 16)}</span>
                    {r.sources.map((s) => (
                      <span key={s} className="rounded-full bg-[var(--ind-06)] px-2 py-[2px] text-[var(--indigo)]">
                        {s}
                      </span>
                    ))}
                    <span className="ml-auto">{r.score.toFixed(3)}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
