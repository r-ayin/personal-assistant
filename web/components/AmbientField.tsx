"use client";

import { useEffect, useRef, useState } from "react";

/**
 * 氛围层：年轮摩尔纹 + 墨晕 + 等高线 + 纸颗粒。
 *
 * 概念仍是「记忆是活有机体」，图形语言是树木年轮：一圈 = 一段时期，
 * 环宽 = 记忆密度，同心层级 = 关系亲疏。
 *
 * 摩尔纹来自两处微差：环距差（A 20 / B 21）+ 转速差（--moire-a/b，反向）。
 *
 * 渲染实现（性能，效果不变）：年轮**一次性光栅化进 canvas 位图**，旋转交给合成器。
 * 原先是两层 ~25 圈的矢量 SVG 每帧旋转——矢量层旋转在多数引擎下无法缓存光栅，
 * 等于每帧重描 50 个圆。位图化后每帧只是旋转两张缓存纹理，视觉完全一致。
 * 位图分辨率上限 MAX_TEX 且 DPR 封顶 1.5，控制纹理内存（约 1600²×4 ≈ 10MB/层）。
 *
 * 标签页隐藏时暂停全部氛围动画（visibilitychange），后台不烧 CPU/GPU。
 *
 * 纯装饰层：pointer-events:none、z-index 0、aria-hidden。
 */

const RING_A_STEP = 20;
const RING_B_STEP = 21;
const RING_MAX = 498;
/** B 层圆心偏移，模拟年轮偏心生长（受光不均，一侧更密） */
const B_OFFSET = { cx: 470, cy: 528 };
/** 位图边长上限（CSS 像素 × DPR 封顶后的物理像素） */
const MAX_TEX = 1600;
const VIEW = 1000;

const COL_RING = "rgba(20,22,26,0.14)";
const COL_MARKER = "rgba(20,22,26,0.24)";
const COL_SEAL = "rgba(214,56,43,0.18)";

function drawRings(canvas: HTMLCanvasElement, step: number, ox: number, oy: number) {
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const cssSize = canvas.clientWidth || MAX_TEX;
  const size = Math.max(512, Math.min(MAX_TEX, Math.floor(cssSize * dpr)));
  if (canvas.width !== size) {
    canvas.width = size;
    canvas.height = size;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, size, size);
  const scale = size / VIEW;
  const cx = ox * scale;
  const cy = oy * scale;
  for (let r = step, i = 1; r <= RING_MAX; r += step, i++) {
    const marker = i % 7 === 0;
    const seal = i % 23 === 0;
    ctx.beginPath();
    ctx.strokeStyle = seal ? COL_SEAL : marker ? COL_MARKER : COL_RING;
    ctx.lineWidth = (seal ? 1.2 : marker ? 1.6 : 1) * scale;
    ctx.arc(cx, cy, r * scale, 0, Math.PI * 2);
    ctx.stroke();
  }
}

/** 等高线：几条横贯视口的平滑曲线（静态，地形质感） */
const CONTOURS = [
  "M-40,180 C180,120 320,240 520,190 S860,90 1080,160",
  "M-40,300 C200,250 300,360 540,310 S880,220 1080,290",
  "M-40,430 C160,390 340,480 560,430 S840,350 1080,420",
  "M-40,560 C220,520 300,610 520,570 S880,490 1080,555",
  "M-40,690 C180,650 360,740 560,690 S860,610 1080,680",
  "M-40,820 C200,780 320,870 540,820 S880,740 1080,810",
];

export default function AmbientField() {
  const aRef = useRef<HTMLCanvasElement>(null);
  const bRef = useRef<HTMLCanvasElement>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const paint = () => {
      if (aRef.current) drawRings(aRef.current, RING_A_STEP, 500, 500);
      if (bRef.current) drawRings(bRef.current, RING_B_STEP, B_OFFSET.cx, B_OFFSET.cy);
    };
    paint();
    let t = 0;
    const onResize = () => {
      window.clearTimeout(t);
      t = window.setTimeout(paint, 200);
    };
    const onVis = () => setHidden(document.hidden);
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return (
    <div aria-hidden="true" data-hidden={hidden ? "true" : undefined}>
      {/* 年轮场：双层差速反转（位图化，旋转由合成器完成） */}
      <div className="ring-field">
        <div className="ring-layer ring-layer-a">
          <canvas ref={aRef} />
        </div>
        <div className="ring-layer ring-layer-b">
          <canvas ref={bRef} />
        </div>
      </div>

      {/* 墨晕 */}
      <div className="ink-wash">
        <div className="ink-blob ink-blob-1" />
        <div className="ink-blob ink-blob-2" />
      </div>

      {/* 等高线 */}
      <div className="contour-field">
        <svg viewBox="0 0 1040 1000" preserveAspectRatio="none">
          {CONTOURS.map((d, i) => (
            <path key={i} d={d} className="contour-line" />
          ))}
        </svg>
      </div>

      {/* 纸颗粒 */}
      <div className="grain" />
    </div>
  );
}
