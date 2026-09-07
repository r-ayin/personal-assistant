import {
  CalendarDays, Compass, FlaskConical, Gauge, Inbox, Layers, LineChart,
  BookOpen, MessageCircle, ScrollText, Search, Settings,
  ShieldCheck, Sparkles, Sunrise, UserRoundCog, Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * 信息架构单一真源。
 *
 * 5 个主导航符合 Cowan 4±1；原先 11 项全平铺既超限，又让「今天」与「推荐」
 * 共用 Sparkles 图标产生歧义。每个主导航下挂 tab，tab 走 ?tab=<id> 查询参数
 * 而非嵌套路由——静态导出下这样能让 tab 切换用 AnimatePresence 做连续转场，
 * 而不是整页重载。
 */

export interface TabDef {
  id: string;
  label: string;
  icon: LucideIcon;
}

export interface NavDef {
  /** 路由，静态导出要求尾斜杠 */
  path: string;
  label: string;
  icon: LucideIcon;
  tabs?: TabDef[];
  /** 重构前的旧路由，访问时客户端重定向到新位置 */
  legacy?: string[];
}

export const NAV: NavDef[] = [
  {
    path: "/today/",
    label: "今天",
    icon: Sunrise,
    tabs: [
      { id: "now", label: "此刻", icon: Compass },
      { id: "schedule", label: "日程", icon: CalendarDays },
      { id: "reminders", label: "提醒", icon: Gauge },
      { id: "recommend", label: "推荐", icon: Sparkles },
    ],
    legacy: ["/", "/calendar/", "/reminders/", "/recommend/"],
  },
  {
    path: "/chat/",
    label: "对话",
    icon: MessageCircle,
    legacy: [],
  },
  {
    path: "/portrait/",
    label: "画像",
    icon: Users,
    tabs: [
      { id: "self", label: "我", icon: UserRoundCog },
      { id: "circles", label: "关系圈", icon: Layers },
      { id: "person", label: "单人档案", icon: Compass },
      { id: "metrics", label: "复杂度指标", icon: LineChart },
      { id: "science", label: "指标科普", icon: FlaskConical },
    ],
    legacy: [],
  },
  {
    path: "/memory/",
    label: "记忆",
    icon: BookOpen,
    tabs: [
      { id: "moments", label: "时刻", icon: ScrollText },
      { id: "search", label: "检索", icon: Search },
      { id: "knowledge", label: "知识", icon: Layers },
    ],
    legacy: ["/memories/", "/wiki/"],
  },
  {
    path: "/system/",
    label: "系统",
    icon: Settings,
    tabs: [
      { id: "ingest", label: "摄入", icon: Inbox },
      { id: "persona", label: "助手人格", icon: UserRoundCog },
      { id: "verify", label: "校验", icon: ShieldCheck },
      { id: "settings", label: "设置", icon: Settings },
    ],
    legacy: ["/inbox/", "/persona/", "/verify/", "/settings/"],
  },
];

/** 旧路由 → 新路由（含默认 tab）。静态导出不支持 next.config redirects，只能客户端跳。
 *  根路由 "/" 不在此列：app/page.tsx 直接渲染「今天」，不做跳转。 */
export const LEGACY_REDIRECTS: Record<string, string> = {
  "/calendar/": "/today/?tab=schedule",
  "/reminders/": "/today/?tab=reminders",
  "/recommend/": "/today/?tab=recommend",
  "/memories/": "/memory/?tab=moments",
  "/wiki/": "/memory/?tab=knowledge",
  "/inbox/": "/system/?tab=ingest",
  "/persona/": "/system/?tab=persona",
  "/verify/": "/system/?tab=verify",
  "/settings/": "/system/?tab=settings",
};

const ALL_LEGACY = Object.keys(LEGACY_REDIRECTS);

/** 归一化 pathname：basePath 是 /web，静态导出带尾斜杠 */
export function normalizePath(pathname: string): string {
  let p = pathname || "/";
  if (p.startsWith("/web")) p = p.slice(4) || "/";
  if (p.length > 1 && !p.endsWith("/")) p += "/";
  return p;
}

export function isActive(navPath: string, pathname: string): boolean {
  const p = normalizePath(pathname);
  if (navPath === "/today/") return p === "/" || p === "/today/";
  return p === navPath;
}

/** 当前 pathname 命中的主导航 */
export function navForPath(pathname: string): NavDef | undefined {
  const p = normalizePath(pathname);
  return NAV.find((n) => (n.path === "/today/" ? p === "/" || p === "/today/" : p === n.path));
}

/** 需要客户端重定向的旧路由（归一化后比较） */
export function legacyTarget(pathname: string): string | undefined {
  const p = normalizePath(pathname);
  if (!ALL_LEGACY.includes(p)) return undefined;
  return LEGACY_REDIRECTS[p];
}

export function defaultTab(nav?: NavDef): string | undefined {
  return nav?.tabs?.[0]?.id;
}
