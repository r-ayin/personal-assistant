"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";

/**
 * canvas 墨滴入水（v4 动效语汇 #5）：投喂区落点晕开的墨滴。
 *
 * 一滴墨 = 主体不规则晕斑（多谐波半径扰动）+ 数颗卫星飞溅 + 一圈扩散淡描边。
 * 颜色不硬编码：运行时经 getComputedStyle 读 --ink-900 / --cinnabar token。
 *
 * reduced-motion / 无高度环境（jsdom）：drop() 直接 no-op，画布保持空白——
 * 第三层降级（组件内判断），不依赖 rAF。
 */

export interface InkDropHandle {
  drop: (x: number, y: number) => void;
}

interface Blot {
  x: number;
  y: number;
  seed: number;
  born: number;
  maxR: number;
  life: number;
  /** 卫星飞溅 */
  sparks: { angle: number; dist: number; r: number }[];
  accent: boolean;
}

const LIFETIME = 1700;

/** token 单一真源是 globals.css；canvas 无法直接吃 var()，运行时读出解析后的值 */
function tokenColor(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const InkDropCanvas = forwardRef<InkDropHandle>(function InkDropCanvas(_, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const blotsRef = useRef<Blot[]>([]);
  const rafRef = useRef<number>(0);
  const reducedRef = useRef(false);

  useEffect(() => {
    reducedRef.current =
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ||
      window.innerHeight === 0;
  }, []);

  /** 画布尺寸跟随容器（含 DPR），仅在挂载与 resize 时处理 */
  const resize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
  }, []);

  useEffect(() => {
    resize();
    // jsdom 没有 ResizeObserver，测试环境直接跳过
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    if (ro && canvasRef.current) ro.observe(canvasRef.current);
    return () => {
      ro?.disconnect();
      cancelAnimationFrame(rafRef.current);
    };
  }, [resize]);

  const frame = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    const now = performance.now();
    const ink = tokenColor("--ink-900");
    const cin = tokenColor("--cinnabar");
    if (!ink) return;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    blotsRef.current = blotsRef.current.filter((b) => now - b.born < b.life);

    for (const b of blotsRef.current) {
      const t = (now - b.born) / b.life; // 0→1
      // 墨入水：先骤然铺开（ink 曲线的滞后进骤扩），后缓慢消散
      const spread = 1 - Math.pow(1 - Math.min(1, t * 2.4), 3);
      const fade = t < 0.55 ? 1 : 1 - (t - 0.55) / 0.45;
      const r = b.maxR * spread;
      const color = b.accent && cin ? cin : ink;

      // 主体：多谐波扰动边缘的不规则晕斑
      ctx.globalAlpha = 0.16 * fade;
      ctx.fillStyle = color;
      ctx.beginPath();
      for (let a = 0; a <= Math.PI * 2 + 0.01; a += Math.PI / 24) {
        const rr =
          r *
          (1 +
            0.16 * Math.sin(a * 3 + b.seed) +
            0.09 * Math.sin(a * 7 - b.seed * 2) +
            0.05 * Math.sin(a * 13 + b.seed * 3));
        const px = b.x + rr * Math.cos(a);
        const py = b.y + rr * Math.sin(a);
        if (a === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();

      // 深色核心
      ctx.globalAlpha = 0.34 * fade * (1 - t * 0.6);
      ctx.beginPath();
      ctx.arc(b.x, b.y, r * 0.28, 0, Math.PI * 2);
      ctx.fill();

      // 扩散描边环
      ctx.globalAlpha = 0.4 * fade;
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(0.6, 2.2 * (1 - t));
      ctx.beginPath();
      ctx.arc(b.x, b.y, r * (0.7 + 0.5 * t), 0, Math.PI * 2);
      ctx.stroke();

      // 卫星飞溅
      for (const s of b.sparks) {
        const d = s.dist * spread;
        ctx.globalAlpha = 0.3 * fade;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(b.x + d * Math.cos(s.angle), b.y + d * Math.sin(s.angle), s.r * (1 - t * 0.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    if (blotsRef.current.length > 0) {
      rafRef.current = requestAnimationFrame(frame);
    } else {
      rafRef.current = 0;
    }
  }, []);

  useImperativeHandle(ref, () => ({
    drop(x: number, y: number) {
      if (reducedRef.current) return; // 降级：不画不跑
      const accent = Math.random() < 0.24; // 偶尔一滴朱砂
      blotsRef.current.push({
        x,
        y,
        seed: Math.random() * Math.PI * 2,
        born: performance.now(),
        maxR: 62 + Math.random() * 46,
        life: LIFETIME + Math.random() * 400,
        accent,
        sparks: Array.from({ length: 5 }, () => ({
          angle: Math.random() * Math.PI * 2,
          dist: 46 + Math.random() * 62,
          r: 1.4 + Math.random() * 2.6,
        })),
      });
      if (!rafRef.current) rafRef.current = requestAnimationFrame(frame);
    },
  }), [frame]);

  return <canvas ref={canvasRef} className="ink-canvas" aria-hidden="true" />;
});

export default InkDropCanvas;
