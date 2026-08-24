"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Bot,
  Brain,
  CalendarClock,
  KeyRound,
  MessageCircle,
  MonitorUp,
  PanelLeftClose,
  Sparkles,
  UserRoundCog,
  UserSearch,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
}

const groups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Today",
    items: [{ path: "/today/", label: "今天", icon: MessageCircle }],
  },
  {
    label: "Assistant",
    items: [
      { path: "/assistant/personality/", label: "性格工作室", icon: UserRoundCog },
      { path: "/assistant/profile/", label: "我的画像", icon: UserSearch },
    ],
  },
  {
    label: "Life",
    items: [
      { path: "/memories/", label: "记忆", icon: Brain },
      { path: "/calendar/", label: "日历与提醒", icon: CalendarClock },
      { path: "/wiki/", label: "知识", icon: BookOpen },
      { path: "/recommend/", label: "推荐", icon: Sparkles },
    ],
  },
  {
    label: "Settings",
    items: [
      { path: "/settings/runtime/", label: "模型与感知", icon: Bot },
      { path: "/settings/barrage/", label: "桌面弹幕", icon: MonitorUp },
      { path: "/settings/connection/", label: "隐私与连接", icon: KeyRound },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname() || "";

  return (
    <aside className="pa-sidebar" aria-label="主导航">
      <div className="pa-brand">
        <div className="pa-brand-mark" aria-hidden="true">P</div>
        <div>
          <strong>Personal Assistant</strong>
          <span>本地工作台</span>
        </div>
        <PanelLeftClose size={15} aria-hidden="true" />
      </div>
      <nav className="pa-nav">
        {groups.map((group) => (
          <section key={group.label} className="pa-nav-group">
            <h2>{group.label}</h2>
            {group.items.map((item) => {
              const active = pathname.startsWith(item.path);
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  aria-current={active ? "page" : undefined}
                  className={active ? "pa-nav-link is-active" : "pa-nav-link"}
                >
                  <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </section>
        ))}
      </nav>
    </aside>
  );
}
