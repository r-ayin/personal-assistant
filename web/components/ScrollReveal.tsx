"use client";

import { useLayoutEffect, useRef, type CSSProperties, type ElementType, type ReactNode } from "react";

/**
 * scroll-driven 揭示 + 视差（gsap ScrollTrigger，v4 动效语汇 #7）。
 *
 * 性能：gsap 改为**挂载后动态 import**。原先静态 import 让 gsap（min 约 70kB）
 * 进首屏 chunk；/today/ 是落地页，等于每个访客都为可能用不到的滚动引擎付费。
 * 动态 import 后 gsap 成为独立异步 chunk，水合完成后才拉取；prefers-reduced-motion
 * 用户与无高度环境（jsdom / 预渲染壳）根本不会触发 import，零下载。
 * 视觉效果不变：滚动揭示与视差照旧，只是就绪晚一帧。
 *
 * 可见性铁律的三重防护：
 *  1. prefers-reduced-motion → 不注册动画，渲染纯静态元素。
 *  2. 无高度环境 → 直接走静态分支，绝不让 gsap 落下 opacity:0 初始态。
 *  3. gsap.context 作用域化 + 卸载 revert，tab 切换反复挂载不泄漏 trigger。
 */

let gsapCore: typeof import("gsap").gsap | null = null;
let scrollTrigger: typeof import("gsap/ScrollTrigger").ScrollTrigger | null = null;
let loader: Promise<void> | null = null;

function loadGsap(): Promise<void> {
  if (!loader) {
    loader = Promise.all([import("gsap"), import("gsap/ScrollTrigger")]).then(([g, s]) => {
      gsapCore = g.gsap;
      scrollTrigger = s.ScrollTrigger;
      gsapCore.registerPlugin(scrollTrigger);
    });
  }
  return loader;
}

export default function ScrollReveal({
  children,
  className,
  style,
  as,
  y = 40,
  parallax = 0,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  as?: ElementType;
  /** 入场位移（px） */
  y?: number;
  /** 视差行程（px），0 = 关闭 */
  parallax?: number;
  delay?: number;
}) {
  const outerRef = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  // jsdom / 预渲染壳没有视口高度或 matchMedia，动效引擎不可信 → 静态可见
  const animatable =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.innerHeight > 0 &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useLayoutEffect(() => {
    if (!animatable || !outerRef.current) return;
    let cancelled = false;
    let ctx: ReturnType<typeof import("gsap").gsap.context> | null = null;

    loadGsap().then(() => {
      if (cancelled || !gsapCore || !scrollTrigger || !outerRef.current) return;
      const g = gsapCore;
      const ST = scrollTrigger;
      ctx = g.context(() => {
        const mm = g.matchMedia();
        mm.add("(prefers-reduced-motion: no-preference)", () => {
          g.fromTo(
            outerRef.current,
            { y, opacity: 0 },
            {
              y: 0,
              opacity: 1,
              duration: 0.9,
              delay,
              ease: "power3.out",
              scrollTrigger: { trigger: outerRef.current, start: "top 92%" },
            },
          );
          if (parallax > 0 && innerRef.current) {
            g.fromTo(
              innerRef.current,
              { y: parallax },
              {
                y: -parallax,
                ease: "none",
                scrollTrigger: {
                  trigger: outerRef.current,
                  start: "top bottom",
                  end: "bottom top",
                  scrub: 0.6,
                },
              },
            );
          }
        });
        // 数据到位后区块高度会变（列表加载、content-visibility 折叠块进入视口），
        // 需要刷新 trigger 位置。但 refresh 会全量重算所有 trigger，成本很高，
        // 连续尺寸变化不防抖就是主线程持续 churn —— 加 160ms 防抖。
        let rt = 0;
        const ro = typeof ResizeObserver !== "undefined"
          ? new ResizeObserver(() => {
              window.clearTimeout(rt);
              rt = window.setTimeout(() => ST.refresh(), 160);
            })
          : null;
        if (ro) ro.observe(outerRef.current!);
        return () => {
          window.clearTimeout(rt);
          ro?.disconnect();
          mm.revert();
        };
      }, outerRef);
    });

    return () => {
      cancelled = true;
      ctx?.revert();
    };
  }, [animatable, y, parallax, delay]);

  const Tag = (as ?? "div") as ElementType;
  // DOM 结构只由 props 决定（与 window 状态无关），预渲染壳与客户端水合才不会错位
  const body = parallax > 0 ? <div ref={innerRef}>{children}</div> : children;

  return (
    <Tag ref={outerRef} className={className} style={style}>
      {body}
    </Tag>
  );
}
