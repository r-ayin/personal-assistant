"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, isActive } from "@/lib/nav";

/**
 * 主导航：5 项（原 11 项全平铺超出 Cowan 4±1，且「今天」与「推荐」共用
 * Sparkles 图标产生歧义）。二级内容改由各页的 TabRail 承载。
 *
 * 激活态用 CSS ::before 的 seal-press 动画——每次切换都是一次"落印"，
 * 比滑动游标更贴合朱砂印章的语义。
 */
export default function Sidebar() {
  const pathname = usePathname() || "";

  return (
    <nav className="pa-sidebar" aria-label="主导航">
      {NAV.map((item) => {
        const active = isActive(item.path, pathname);
        const Icon = item.icon;
        return (
          <Link
            key={item.path}
            href={item.path}
            title={item.label}
            aria-label={item.label}
            aria-current={active ? "page" : undefined}
            className={`nav-item ${active ? "is-active" : ""}`}
          >
            <span className="nav-icon">
              <Icon size={20} strokeWidth={active ? 2 : 1.5} />
            </span>
            <span className="nav-label">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
