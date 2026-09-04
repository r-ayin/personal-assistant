"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { EASE } from "@/lib/motion";

/**
 * 证据墨点：助手回答召回的记忆化作一排靛青墨点。
 * 悬浮/聚焦某粒墨点时，在其下方展开瓷面浮层小卡，逐条展示证据原文。
 * 绝不用原生 title 敷衍。
 */
export function EvidenceEmbers({ evidence }: { evidence: string[] }) {
  const items = evidence.map((e) => (e || "").trim()).filter(Boolean);
  if (items.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
      <span
        className="serif"
        style={{ fontSize: 11, letterSpacing: "0.1em", color: "var(--text-weak)" }}
      >
        召回的余烬
      </span>
      <div className="flex flex-wrap items-center gap-2.5">
        {items.map((text, i) => (
          <EmberDot key={`${i}-${text.slice(0, 16)}`} text={text} index={i} total={items.length} />
        ))}
      </div>
    </div>
  );
}

function EmberDot({ text, index, total }: { text: string; index: number; total: number }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {/* 入场缩放由 motion 负责；悬浮发光由内层按钮负责，避免 transform 冲突 */}
      <motion.span
        initial={{ opacity: 0, scale: 0.4 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.4 + index * 0.12, duration: 0.6, ease: EASE.out }}
        className="inline-flex"
      >
        <button
          type="button"
          aria-label={`证据余烬 ${index + 1}，共 ${total} 缕，查看原文`}
          aria-expanded={open}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onClick={() => setOpen((v) => !v)}
          className="block h-2.5 w-2.5 cursor-pointer rounded-full border-0 p-0"
          style={{
            background: "var(--indigo)",
            boxShadow: open ? "0 0 12px var(--ind-40)" : "0 0 5px var(--ind-25)",
            transform: open ? "scale(1.3)" : "scale(1)",
            transition: "box-shadow 0.5s var(--ease-out), transform 0.5s var(--ease-out)",
          }}
        />
      </motion.span>
      <AnimatePresence>
        {open && (
          <motion.div
            role="tooltip"
            initial={{ opacity: 0, y: -6, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -4, filter: "blur(4px)" }}
            transition={{ duration: 0.5, ease: EASE.out }}
            className="absolute left-0 top-full z-30 mt-3 w-max max-w-[300px]"
            style={{ marginLeft: -8, pointerEvents: "none" }}
          >
            <div
              className="relative"
              style={{
                background: "linear-gradient(165deg, var(--porcelain-2), var(--porcelain-1))",
                border: "1px solid var(--ind-25)",
                borderRadius: 14,
                boxShadow: "0 14px 36px -14px var(--ink-12), 0 0 18px var(--ind-10)",
                backdropFilter: "blur(14px)",
                padding: "12px 16px",
              }}
            >
              {/* 小三角指向余烬 */}
              <span
                aria-hidden
                className="absolute block h-2.5 w-2.5"
                style={{
                  left: 10,
                  top: -5,
                  transform: "rotate(45deg)",
                  background: "var(--porcelain-2)",
                  borderLeft: "1px solid var(--ind-25)",
                  borderTop: "1px solid var(--ind-25)",
                }}
              />
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.14em",
                  color: "var(--indigo)",
                }}
              >
                余烬 {index + 1} / {total}
              </div>
              <p
                className="serif whitespace-pre-wrap text-left"
                style={{ fontSize: 13, lineHeight: 1.9, color: "var(--text-dim)", marginTop: 6 }}
              >
                {text}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}
