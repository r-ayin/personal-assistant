"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import EmptyState from "@/components/EmptyState";
import InkDropCanvas, { type InkDropHandle } from "@/components/InkDropCanvas";
import { LoadingDots, SectionHeader, Tag, WhisperLine } from "@/components/ui";
import { api } from "@/lib/api";
import { speakerLabel } from "@/lib/labels";
import { EASE } from "@/lib/motion";
import type { TagColor } from "@/components/ui";
import type { Segment } from "@/lib/types";

const ACCEPTED_EXTENSIONS = [".txt", ".srt"];

type FileStatus = "waiting" | "uploading" | "done" | "error";

interface UploadItem {
  id: string;
  name: string;
  size: number;
  status: FileStatus;
  note?: string;
}

const STATUS_CHIP: Record<FileStatus, { label: string; color: TagColor }> = {
  waiting: { label: "等待", color: "ochre" },
  uploading: { label: "上传中", color: "indigo" },
  done: { label: "已入火", color: "mineral" },
  error: { label: "未入火", color: "cinnabar" },
};

function isAccepted(name: string): boolean {
  const n = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => n.endsWith(ext));
}

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 等宽时间：MM-DD HH:mm，解析失败则截原串 */
function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return (iso || "").slice(0, 16);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 「系统 · 摄入」面板：原 /inbox/ 的全部内容。外壳由 DestinationPage 提供。 */
export default function IngestPanel() {
  const [dragging, setDragging] = useState(false);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [ingestPhase, setIngestPhase] = useState<"idle" | "ingesting" | "done" | "error">("idle");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [segTotal, setSegTotal] = useState(0);
  const [segState, setSegState] = useState<"loading" | "ready" | "error">("loading");
  const dropRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const inkRef = useRef<InkDropHandle>(null);

  /* 「已吸收的回响」：最近 30 段，倒序 */
  const loadSegments = useCallback(async () => {
    const res = await api.segments("30");
    if (!res) {
      setSegState("error");
      return;
    }
    setSegments([...res.segments].reverse());
    setSegTotal(res.total);
    setSegState("ready");
  }, []);

  useEffect(() => {
    void loadSegments();
  }, [loadSegments]);

  /* 墨滴入水：落点交给 canvas 晕开（reduced-motion 时组件内自行 no-op） */
  const addRipple = useCallback((x: number, y: number) => {
    inkRef.current?.drop(x, y);
  }, []);

  const rippleAtCenter = useCallback(() => {
    const el = dropRef.current;
    if (el) addRipple(el.clientWidth / 2, el.clientHeight / 2);
  }, [addRipple]);

  /* 逐文件上传；全部成功后自动 ingest 吸收，并刷新回响 */
  const processFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0 || busy) return;
      setBusy(true);
      setIngestPhase("idle");
      const items: UploadItem[] = files.map((f, i) => {
        const ok = isAccepted(f.name);
        return {
          id: `${Date.now()}-${i}-${f.name}`,
          name: f.name,
          size: f.size,
          status: ok ? ("waiting" as const) : ("error" as const),
          note: ok ? undefined : "只收 .txt / .srt 的薪柴",
        };
      });
      setUploads((prev) => [...items, ...prev]);

      const accepted: { item: UploadItem; file: File }[] = [];
      items.forEach((item, i) => {
        if (item.status === "waiting") accepted.push({ item, file: files[i] });
      });

      let allOk = accepted.length > 0;
      for (const { item, file } of accepted) {
        setUploads((prev) => prev.map((u) => (u.id === item.id ? { ...u, status: "uploading" } : u)));
        try {
          const buffer = await file.arrayBuffer();
          const res = await api.uploadInbox(file.name, buffer);
          if (res === null) throw new Error("upload rejected");
          setUploads((prev) => prev.map((u) => (u.id === item.id ? { ...u, status: "done" } : u)));
        } catch {
          allOk = false;
          setUploads((prev) =>
            prev.map((u) =>
              u.id === item.id
                ? { ...u, status: "error", note: "这束薪柴没燃起来，稍后再试" }
                : u,
            ),
          );
        }
      }

      if (allOk) {
        setIngestPhase("ingesting");
        const res = await api.ingest();
        if (res === null) {
          setIngestPhase("error");
        } else {
          setIngestPhase("done");
          void loadSegments();
        }
      }
      setBusy(false);
    },
    [busy, loadSegments],
  );

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    const rect = dropRef.current?.getBoundingClientRect();
    addRipple(e.clientX - (rect?.left ?? 0), e.clientY - (rect?.top ?? 0));
    void processFiles(Array.from(e.dataTransfer.files || []));
  }

  function handlePick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      rippleAtCenter();
      void processFiles(files);
    }
    e.target.value = "";
  }

  return (
    <div className="mx-auto max-w-[860px]">
      <WhisperLine>薪入火，涟漪起——菌林会记住每一粒字</WhisperLine>

      {/* 大拖拽区：虚线发丝边，拖入时转暖金 + 背景微光 */}
      <section className="mt-8">
        <div
          ref={dropRef}
          role="button"
          tabIndex={0}
          aria-label="投喂薪柴：拖入或点击选择 .txt / .srt 文件，可多选"
          onClick={() => fileRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileRef.current?.click();
            }
          }}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className="relative flex cursor-pointer flex-col items-center justify-center overflow-hidden text-center"
          style={{
            height: 260,
            borderRadius: 20,
            border: dragging ? "1.5px dashed var(--indigo)" : "1.5px dashed var(--edge)",
            background: dragging
              ? "linear-gradient(170deg, var(--ind-06), var(--porcelain-2))"
              : "linear-gradient(170deg, var(--porcelain-2), transparent)",
            boxShadow: dragging
              ? "0 0 28px var(--ind-10), inset 0 0 36px var(--ind-06)"
              : "none",
            transition:
              "border-color 0.6s var(--ease-out), background 0.6s var(--ease-out), box-shadow 0.6s var(--ease-out)",
          }}
        >
          <InkDropCanvas ref={inkRef} />
          <span className="empty-seed-dot" style={{ width: 14, height: 14 }} />
          <p className="serif mt-5" style={{ fontSize: 18, color: "var(--text-main)" }}>
            {dragging ? "松手，让薪柴落入火中" : "把文字与声音投进来"}
          </p>
          <p className="mt-2 text-[13px]" style={{ color: "var(--text-weak)" }}>
            支持 .txt / .srt · 可多选 · 点击亦可选择
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.srt"
            multiple
            className="hidden"
            onChange={handlePick}
            aria-hidden
            tabIndex={-1}
          />
        </div>
      </section>

      {/* 薪柴入火：逐文件状态（数据驱动的进出场，保留 AnimatePresence） */}
      {uploads.length > 0 && (
        <section className="mt-12">
          <SectionHeader
            title="薪柴入火"
            subtitle="每一束文字，都会被慢慢记住"
            right={
              !busy ? (
                <button
                  type="button"
                  className="btn-ghost !px-4 !py-1.5 text-xs"
                  onClick={() => {
                    setUploads([]);
                    setIngestPhase("idle");
                  }}
                >
                  拂去灰烬
                </button>
              ) : undefined
            }
          />
          <div className="space-y-3">
            <AnimatePresence initial={false}>
              {uploads.map((u) => (
                <motion.div
                  key={u.id}
                  layout
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.6, ease: EASE.out }}
                  className="glass-card flex items-center gap-4 px-5 py-4"
                >
                  {u.status === "uploading" ? (
                    <span
                      className="empty-seed-dot"
                      style={{ width: 8, height: 8, flex: "0 0 auto" }}
                    />
                  ) : (
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{
                        flex: "0 0 auto",
                        background:
                          u.status === "done"
                            ? "var(--mineral)"
                            : u.status === "error"
                              ? "var(--cinnabar)"
                              : "var(--ochre)",
                      }}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm" style={{ color: "var(--text-main)" }}>
                      {u.name}
                    </div>
                    <div className="mt-1 flex items-center gap-3">
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          color: "var(--text-weak)",
                        }}
                      >
                        {formatSize(u.size)}
                      </span>
                      {u.note && (
                        <span style={{ fontSize: 12, color: "var(--text-weak)" }}>{u.note}</span>
                      )}
                    </div>
                  </div>
                  <Tag color={STATUS_CHIP[u.status].color}>{STATUS_CHIP[u.status].label}</Tag>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          <AnimatePresence>
            {ingestPhase !== "idle" && (
              <motion.div
                key={ingestPhase}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.6, ease: EASE.out }}
                className="mt-5 flex justify-center"
              >
                {ingestPhase === "ingesting" && (
                  <LoadingDots label="薪已入火，菌林正在记住……" />
                )}
                {ingestPhase === "done" && (
                  <span className="serif" style={{ fontSize: 13, color: "var(--mineral-deep)" }}>
                    薪已入火——回响正在下方浮现
                  </span>
                )}
                {ingestPhase === "error" && (
                  <span className="serif" style={{ fontSize: 13, color: "var(--ochre-deep)" }}>
                    （火还温着，但这一刻没能化开薪柴，稍后再试）
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      )}

      {/* 已吸收的回响 */}
      <section className="mt-16">
        <SectionHeader
          title="已吸收的回响"
          subtitle="菌林记住的只言片语"
          right={
            segTotal > 0 ? (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-weak)",
                }}
              >
                {segTotal} 段回响
              </span>
            ) : undefined
          }
        />
        {segState === "loading" && (
          <div className="flex justify-center py-12">
            <LoadingDots label="正在聆听回响……" />
          </div>
        )}
        {segState === "error" && <EmptyState message="炉火熄了——回响暂时听不清" />}
        {segState === "ready" && segments.length === 0 && (
          <EmptyState message="把文字与声音投进来，菌林会记住" />
        )}
        {segState === "ready" && segments.length > 0 && (
          <div className="space-y-3">
            {segments.map((seg, i) => (
              <motion.article
                key={seg.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, ease: EASE.out, delay: Math.min(i * 0.05, 0.6) }}
                className="glass-card px-5 py-4"
              >
                <div className="flex items-center gap-3">
                  <Tag color="indigo">{speakerLabel(seg.speaker) || "无名之声"}</Tag>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      letterSpacing: "0.06em",
                      color: "var(--text-weak)",
                    }}
                  >
                    {formatTime(seg.created_at)}
                  </span>
                  {seg.source_file && (
                    <span
                      className="ml-auto max-w-[40%] truncate"
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--text-weak)",
                      }}
                    >
                      {seg.source_file}
                    </span>
                  )}
                </div>
                <p
                  className="mt-2.5 text-sm"
                  style={{
                    color: "var(--text-dim)",
                    lineHeight: 1.9,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {seg.text}
                </p>
              </motion.article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
