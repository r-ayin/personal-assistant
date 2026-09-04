import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import StatusStrip from "@/components/StatusStrip";
import PendingPanel from "@/components/panels/PendingPanel";
import RootPage from "@/app/page";
import TodayPage from "@/app/today/page";
import ChatPage from "@/app/chat/page";
import MemoryPage from "@/app/memory/page";
import PortraitPage from "@/app/portrait/page";
import SystemPage from "@/app/system/page";
import { LEGACY_REDIRECTS, isActive, legacyTarget, navForPath } from "@/lib/nav";
import { api, clearApiToken, getApiToken, setApiToken } from "@/lib/api";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));
vi.mocked(usePathname).mockReturnValue("/");

// Mock framer-motion to avoid animation issues in tests.
// 沿用旧手法：motion.* 一律降级成同名的静态 DOM 标签，动画 props 经 filterDomProps 滤掉。
// 新增两点，因为新外壳（Reveal / TabRail / PageTransition / TabPanel）会用到：
//   · useReducedMotion 返回 true —— 让这些组件走「纯静态可见」分支，测试里确定且不依赖 rAF；
//   · 覆盖到全部实际用到的标签（section/article/p/button/circle/path/g/text），
//     否则取到 undefined 会直接渲染崩。
vi.mock("framer-motion", () => {
  const tag = (name: string) => {
    const Tag = name as unknown as React.ElementType;
    return (props: Record<string, unknown>) => <Tag {...filterDomProps(props)} />;
  };
  return {
    motion: {
      div: tag("div"),
      span: tag("span"),
      p: tag("p"),
      section: tag("section"),
      article: tag("article"),
      button: tag("button"),
      circle: tag("circle"),
      path: tag("path"),
      g: tag("g"),
      text: tag("text"),
    },
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useReducedMotion: () => true,
  };
});

function filterDomProps(props: Record<string, unknown>) {
  const dom: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (
      k.startsWith("initial") || k.startsWith("animate") || k.startsWith("exit") ||
      k.startsWith("transition") || k.startsWith("while") || k.startsWith("onAnimation") ||
      k === "variants" || k === "layout" || k === "layoutId" ||
      k === "custom" || k === "viewport"
    ) continue;
    dom[k] = v;
  }
  return dom;
}

/** 各面板挂载即取数；给一个「一切正常但空空如也」的后端，免得测试里冒出未处理的 rejection */
const EMPTY_BACKEND = {
  events: [], reminders: [], moments: [], memories: [], segments: [], total: 0,
  topics: [], pages: [], items: [], chat_log: [], recommendations: [], feedback: [],
};

/** 挂载即取数的面板会在同步断言之后才 resolve；用 act 排空微任务，避免 act(...) 警告 */
async function flushEffects() {
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(EMPTY_BACKEND), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearApiToken();
  delete window.PA_TOKEN;
  vi.mocked(usePathname).mockReturnValue("/");
});

describe("Sidebar navigation", () => {
  it("renders the 5 primary destinations", () => {
    render(<Sidebar />);
    expect(screen.getByText("今天")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
    expect(screen.getByText("画像")).toBeInTheDocument();
    expect(screen.getByText("记忆")).toBeInTheDocument();
    expect(screen.getByText("系统")).toBeInTheDocument();
  });

  it("no longer flattens the 11 legacy items into the rail", () => {
    render(<Sidebar />);
    // 这些原先都是主导航项，现在降级为 tab 或已移除
    for (const gone of ["投喂", "日历", "知识", "档案", "提醒", "推荐", "校验", "设置"]) {
      expect(screen.queryByText(gone)).not.toBeInTheDocument();
    }
    expect(screen.queryByText("桌面弹幕")).not.toBeInTheDocument();
    expect(screen.queryByText("模型与感知")).not.toBeInTheDocument();
    expect(screen.queryByText("性格工作室")).not.toBeInTheDocument();
  });

  it("把根路由认作「今天」", () => {
    expect(isActive("/today/", "/")).toBe(true);
    expect(isActive("/today/", "/web/today/")).toBe(true);
    expect(navForPath("/web/memory/")?.label).toBe("记忆");
  });
});

describe("Destinations render", () => {
  it("根路由 = 今天，带 4 个 tab 且默认停在「此刻」", () => {
    vi.mocked(usePathname).mockReturnValue("/");
    render(<RootPage />);
    expect(screen.getByRole("heading", { level: 1, name: "今天" })).toBeInTheDocument();
    for (const label of ["此刻", "日程", "提醒", "推荐"]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(document.getElementById("panel-now")).toBeInTheDocument();
  });

  it("/today/ 与根路由渲染同一个目的地", () => {
    vi.mocked(usePathname).mockReturnValue("/today/");
    render(<TodayPage />);
    expect(screen.getByRole("heading", { level: 1, name: "今天" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(4);
    expect(document.getElementById("panel-now")).toBeInTheDocument();
  });

  it("切 tab 会换成对应面板并把标题跟着改", async () => {
    vi.mocked(usePathname).mockReturnValue("/today/");
    render(<TodayPage />);
    fireEvent.click(screen.getByRole("tab", { name: /日程/ }));
    await waitFor(() => {
      expect(document.getElementById("panel-schedule")).toBeInTheDocument();
    });
    expect(document.getElementById("panel-now")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "日程" })).toBeInTheDocument();
  });

  it("/chat/ 只有外壳、没有 tab", async () => {
    vi.mocked(usePathname).mockReturnValue("/chat/");
    render(<ChatPage />);
    expect(screen.getByRole("heading", { level: 1, name: "对话" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "输入想对菌林说的话" })).toBeInTheDocument();
    await flushEffects();
  });

  it("/memory/ 带 3 个 tab，检索接真实端点且状态诚实", async () => {
    vi.mocked(usePathname).mockReturnValue("/memory/");
    render(<MemoryPage />);
    // h1 跟随当前 tab：默认 moments → 「时刻」
    expect(screen.getByRole("heading", { level: 1, name: "时刻" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(3);

    fireEvent.click(screen.getByRole("tab", { name: /检索/ }));
    await waitFor(() => {
      expect(document.getElementById("panel-search")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 1, name: "检索" })).toBeInTheDocument();
    // 诚实状态之一：未提交 / 加载中 / 连不上 / 无命中；绝不编造结果
    expect(screen.getByText(/输入关键词|检索中|连不上后端|没有命中/)).toBeInTheDocument();
  });

  it("/portrait/ 4 个 tab 接真实端点，空/错时诚实降级不编造", async () => {
    vi.mocked(usePathname).mockReturnValue("/portrait/");
    render(<PortraitPage />);
    expect(screen.getByRole("heading", { level: 1, name: "我" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(4);
    await waitFor(() => {
      expect(screen.getByText(/正在从消息里读取|连不上后端|画像库尚未建立|画像正在从你的消息里长出来/))
        .toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: /复杂度指标/ }));
    await waitFor(() => {
      expect(document.getElementById("panel-metrics")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { level: 1, name: "复杂度指标" })).toBeInTheDocument();
    expect(screen.getByText(/正在读取指标|连不上后端|指标库尚未建立|还没有任何指标/)).toBeInTheDocument();
  });

  it("/system/ 带 4 个 tab，默认停在摄入", () => {
    vi.mocked(usePathname).mockReturnValue("/system/");
    render(<SystemPage />);
    expect(screen.getByRole("heading", { level: 1, name: "系统" })).toBeInTheDocument();
    for (const label of ["摄入", "助手人格", "校验", "设置"]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(document.getElementById("panel-ingest")).toBeInTheDocument();
  });
});

describe("PendingPanel", () => {
  it("说明在等哪个后端阶段，并列出具体的 needs", () => {
    render(
      <PendingPanel
        title="单人档案"
        waiting="后端 P2 + P5"
        needs={["5950 个发言者标签归并到 person_id", "共现网络构建"]}
      />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "单人档案" })).toBeInTheDocument();
    expect(screen.getByText(/后端 P2 \+ P5/)).toBeInTheDocument();
    expect(screen.getByText("5950 个发言者标签归并到 person_id")).toBeInTheDocument();
    expect(screen.getByText("共现网络构建")).toBeInTheDocument();
    expect(screen.getByText(/不放任何示例数字/)).toBeInTheDocument();
  });

  it("needs 可省略", () => {
    render(<PendingPanel title="关系圈" waiting="后端 P2：跨会话人物身份归并尚未完成" />);
    expect(screen.getByRole("heading", { level: 2, name: "关系圈" })).toBeInTheDocument();
    expect(screen.queryByText("接通它需要")).not.toBeInTheDocument();
  });
});

describe("Legacy redirects", () => {
  it("9 个旧路由都能算出新目标（含尾斜杠与 basePath 归一化）", () => {
    const expected: Record<string, string> = {
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
    expect(Object.keys(LEGACY_REDIRECTS)).toHaveLength(9);
    for (const [from, to] of Object.entries(expected)) {
      expect(legacyTarget(from)).toBe(to);
      // 静态导出带尾斜杠，但访问时也可能没有
      expect(legacyTarget(from.slice(0, -1))).toBe(to);
      expect(legacyTarget(`/web${from}`)).toBe(to);
    }
  });

  it("根路由不是重定向目标——它就是今天", () => {
    expect(legacyTarget("/")).toBeUndefined();
    expect(legacyTarget("/today/")).toBeUndefined();
  });
});

describe("StatusStrip", () => {
  it("renders the breathing bar", async () => {
    const { container } = render(<StatusStrip />);
    expect(container.querySelector(".status-bar")).toBeInTheDocument();
    await flushEffects();
  });
});

describe("API error contracts", () => {
  it("preserves HTTP status and parsed details on required methods", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "stale version", current_version: 8 }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    )));

    const request = api.updateAssistantPersonality({
      preset_id: "gentle", name: "PA", user_address: "你",
      directness: 2, humor: 2, initiative: "balanced",
      reply_length: "balanced", barrage_style: "light", taboos: [], custom_instruction: "",
      expected_version: 7,
    });
    await expect(request).rejects.toMatchObject({
      status: 409,
      path: "/assistant/personality",
      details: { detail: "stale version", current_version: 8 },
    });
  });

  it("uses DELETE for feedback deactivation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "feedback-1", active: false }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.deleteProfileFeedback("feedback-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/profile/feedback/feedback-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("仅在已有 conversation id 时写入聊天请求体", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ reply: "第一条", evidence: [], conversation_id: "conversation-1" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ reply: "第二条", evidence: [], conversation_id: "conversation-1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.chat("第一条消息");
    await api.chat("第二条消息", "conversation-1");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({ message: "第一条消息" });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string)).toEqual({
      message: "第二条消息",
      conversation_id: "conversation-1",
    });
  });
});

describe("Token management", () => {
  it("prefers window.PA_TOKEN over the session token", () => {
    sessionStorage.setItem("pa-api-token", "session-token");
    window.PA_TOKEN = "injected-token";
    expect(getApiToken()).toBe("injected-token");
  });

  it("stores token in sessionStorage only", () => {
    setApiToken("test-token");
    expect(sessionStorage.getItem("pa-api-token")).toBe("test-token");
    expect(localStorage.getItem("pa-api-token")).toBeNull();
  });

  it("clears token correctly", () => {
    setApiToken("to-clear");
    clearApiToken();
    expect(sessionStorage.getItem("pa-api-token")).toBeNull();
  });
});
