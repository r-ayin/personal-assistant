import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import PersonalityPage from "@/app/assistant/personality/page";
import ProfilePage from "@/app/assistant/profile/page";
import RuntimePage from "@/app/settings/runtime/page";
import BarragePage from "@/app/settings/barrage/page";
import ConnectionPage from "@/app/settings/connection/page";
import { ApiError, api, clearApiToken, getApiToken } from "@/lib/api";
import type {
  AssistantPersonality,
  BarrageSettings,
  ProfileResponse,
  RuntimeStatus,
} from "@/lib/types";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));
vi.mocked(usePathname).mockReturnValue("/today/");

const personality: AssistantPersonality = {
  preset_id: "gentle",
  name: "PA",
  user_address: "你",
  directness: 2,
  humor: 2,
  initiative: "balanced",
  reply_length: "balanced",
  barrage_style: "restrained",
  taboos: [],
  custom_instruction: "",
  version: 7,
  created_at: "2026-07-31T09:00:00Z",
};

const modelStatus: RuntimeStatus = {
  state: "ready",
  running: true,
  error: "",
  consumers: ["manual", "perception"],
};

const barrageSettings: BarrageSettings = {
  enabled: true,
  quiet_mode: false,
  paused_until: "",
  position: "top",
  font_size: 24,
  opacity: 0.8,
  duration_seconds: 8,
  theme: "contrast",
  display_id: "primary",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function mockPersonalityLoad() {
  vi.spyOn(api, "assistantPersonality").mockResolvedValue(personality);
  vi.spyOn(api, "previewAssistantPersonality").mockResolvedValue({
    chat: "你，我是 PA。聊天示例。",
    reminder: "你，约定的提醒时间到了。",
    perception: "你，我注意到一个变化。",
  });
}

function mockRuntimeLoad() {
  vi.spyOn(api, "health").mockResolvedValue({ status: "ok", segments: 2, memories: 3 });
  vi.spyOn(api, "localModelStatus").mockResolvedValue(modelStatus);
  vi.spyOn(api, "barrageStatus").mockResolvedValue({
    settings: barrageSettings,
    overlay_clients: 1,
    paused: false,
  });
  vi.spyOn(api, "llmSettings").mockResolvedValue({ backend: "minicpm_o", model: "MiniCPM-o" });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearApiToken();
  delete window.PA_TOKEN;
  vi.mocked(usePathname).mockReturnValue("/today/");
});

describe("Personality Studio", () => {
  it("applies a preset only to the unsaved draft", async () => {
    mockPersonalityLoad();
    const save = vi.spyOn(api, "updateAssistantPersonality");
    render(<PersonalityPage />);

    await screen.findByDisplayValue("PA");
    fireEvent.click(screen.getByRole("button", { name: "理性克制" }));
    expect(screen.getByLabelText("直接程度")).toHaveValue("4");
    expect(screen.getByLabelText("幽默程度")).toHaveValue("1");
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByText("有未保存修改")).toBeInTheDocument();
  });

  it("refreshes all three preview examples from the unsaved draft", async () => {
    mockPersonalityLoad();
    render(<PersonalityPage />);

    await screen.findByDisplayValue("PA");
    fireEvent.change(screen.getByLabelText("助手名字"), { target: { value: "阿简" } });
    fireEvent.click(screen.getByRole("button", { name: "更新预览" }));

    await waitFor(() =>
      expect(api.previewAssistantPersonality).toHaveBeenCalledWith(
        expect.objectContaining({ name: "阿简" }),
      ),
    );
    expect(screen.getByText("你，我是 PA。聊天示例。")).toBeInTheDocument();
    expect(screen.getByText("你，约定的提醒时间到了。")).toBeInTheDocument();
    expect(screen.getByText("你，我注意到一个变化。")).toBeInTheDocument();
  });

  it("saves with expected_version", async () => {
    mockPersonalityLoad();
    const save = vi
      .spyOn(api, "updateAssistantPersonality")
      .mockResolvedValue({ ...personality, name: "阿简", version: 8 });
    render(<PersonalityPage />);

    await screen.findByDisplayValue("PA");
    fireEvent.change(screen.getByLabelText("助手名字"), { target: { value: "阿简" } });
    fireEvent.click(screen.getByRole("button", { name: "保存性格" }));

    await waitFor(() =>
      expect(save).toHaveBeenCalledWith(expect.objectContaining({ name: "阿简", expected_version: 7 })),
    );
  });

  it("preserves edits and shows the exact 409 conflict message", async () => {
    mockPersonalityLoad();
    vi.spyOn(api, "updateAssistantPersonality").mockRejectedValue(
      new ApiError("version conflict", 409, "/assistant/personality", { detail: "version conflict" }),
    );
    render(<PersonalityPage />);

    await screen.findByDisplayValue("PA");
    fireEvent.change(screen.getByLabelText("助手名字"), { target: { value: "保留这个草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "保存性格" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "性格配置已在其他页面更新，请重新加载后合并修改。",
    );
    expect(screen.getByLabelText("助手名字")).toHaveValue("保留这个草稿");
  });
});

describe("Profile feedback", () => {
  const profile: ProfileResponse = {
    inferred: { preferences: ["咖啡"], goals: ["完成评审"] },
    effective: { preferences: ["咖啡", "茶"], goals: ["完成评审"] },
    version: 4,
    change_summary: "依据 memory:m1 更新",
    feedback: [
      {
        id: "feedback-1",
        dimension: "preferences",
        value: "茶",
        action: "add",
        evidence_kind: "user_statement",
        evidence: "用户明确说更喜欢茶",
        active: true,
        created_at: "2026-07-31T09:00:00Z",
      },
    ],
  };

  it("separates inferred, effective and feedback evidence", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    render(<ProfilePage />);

    const inferred = await screen.findByTestId("profile-inferred");
    const effective = screen.getByTestId("profile-effective");
    const evidence = screen.getByTestId("profile-evidence");
    expect(within(inferred).getByText("咖啡")).toBeInTheDocument();
    expect(within(effective).getByText("茶")).toBeInTheDocument();
    expect(within(evidence).getByText(/用户明确说更喜欢茶/)).toBeInTheDocument();
    expect(screen.queryByText("弹幕风格")).not.toBeInTheDocument();
  });

  it("can add or suppress known dimensions and deactivate feedback", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    const add = vi.spyOn(api, "addProfileFeedback").mockResolvedValue({ id: "feedback-2", active: true });
    const remove = vi.spyOn(api, "deleteProfileFeedback").mockResolvedValue({ id: "feedback-1", active: false });
    render(<ProfilePage />);

    await screen.findByText(/用户明确说更喜欢茶/);
    fireEvent.change(screen.getByLabelText("画像维度"), { target: { value: "preferences" } });
    fireEvent.change(screen.getByLabelText("反馈内容"), { target: { value: "不喝咖啡" } });
    fireEvent.change(screen.getByLabelText("反馈依据"), { target: { value: "我明确说明不喝咖啡" } });
    fireEvent.click(screen.getByRole("button", { name: "抑制此项" }));

    await waitFor(() =>
      expect(add).toHaveBeenCalledWith({
        dimension: "preferences",
        value: "不喝咖啡",
        action: "suppress",
        evidence_kind: "user_statement",
        evidence: "我明确说明不喝咖啡",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "停用反馈：茶" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith("feedback-1"));
  });
});

describe("Runtime controls", () => {
  it("stops perception through /perception/stop and renders returned model state", async () => {
    mockRuntimeLoad();
    const stop = vi.spyOn(api, "stopPerception").mockResolvedValue({
      perception: "stopped",
      local_model: { ...modelStatus, state: "stopped", running: false, consumers: ["manual"] },
    });
    render(<RuntimePage />);

    await screen.findByText("MiniCPM-o");
    fireEvent.click(screen.getByRole("button", { name: "停止感知" }));

    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
    expect(screen.getByTestId("runtime-model")).toHaveTextContent("stopped");
  });

  it("renders PA, model, perception and overlay independently", async () => {
    mockRuntimeLoad();
    render(<RuntimePage />);

    await screen.findByText("MiniCPM-o");
    expect(screen.getByTestId("runtime-pa")).toHaveTextContent("ok");
    expect(screen.getByTestId("runtime-model")).toHaveTextContent("ready");
    expect(screen.getByTestId("runtime-perception")).toHaveTextContent("running");
    expect(screen.getByTestId("runtime-overlay")).toHaveTextContent("connected");
    expect(screen.getByText("manual")).toBeInTheDocument();
    expect(screen.getByText("perception")).toBeInTheDocument();
  });
});

describe("API error contracts", () => {
  it("preserves HTTP status and parsed details on required methods", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "stale version", current_version: 8 }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    )));

    const request = api.updateAssistantPersonality({ ...personality, expected_version: 7 });
    await expect(request).rejects.toMatchObject({
      status: 409,
      path: "/assistant/personality",
      details: { detail: "stale version", current_version: 8 },
    });
  });

  it("uses PUT for barrage settings and DELETE for feedback deactivation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(barrageSettings), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "feedback-1", active: false }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.updateBarrageSettings({ opacity: 0.6 });
    await api.deleteProfileFeedback("feedback-1");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/barrage/settings", expect.objectContaining({ method: "PUT" }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/profile/feedback/feedback-1", expect.objectContaining({ method: "DELETE" }));
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

describe("Local model confirmation", () => {
  it("confirms immediately before starting the local model", async () => {
    mockRuntimeLoad();
    vi.spyOn(api, "localModelStatus").mockResolvedValue({ ...modelStatus, state: "stopped", running: false, consumers: [] });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const start = vi.spyOn(api, "startLocalModel").mockResolvedValue(modelStatus);
    render(<RuntimePage />);

    await screen.findByText("MiniCPM-o");
    fireEvent.click(screen.getByRole("button", { name: "启动模型" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(start).not.toHaveBeenCalled();
  });
});

describe("Barrage settings", () => {
  it("calls the backend test endpoint and never claims local delivery", async () => {
    vi.spyOn(api, "barrageSettings").mockResolvedValue(barrageSettings);
    vi.spyOn(api, "barrageStatus").mockResolvedValue({ settings: barrageSettings, overlay_clients: 1, paused: false });
    const pending = deferred<{ id: string; kind: string; priority: "low"; text: string; created_at: string; expires_at: string; personality_version: number; style: string; assistant_name: string; evidence: string }>();
    const testBarrage = vi.spyOn(api, "testBarrage").mockReturnValue(pending.promise);
    render(<BarragePage />);

    await screen.findAllByDisplayValue("24");
    fireEvent.click(screen.getByRole("button", { name: "发送测试弹幕" }));
    expect(testBarrage).toHaveBeenCalledOnce();
    expect(screen.queryByText(/已投递/)).not.toBeInTheDocument();

    pending.resolve({
      id: "event-42",
      kind: "test",
      priority: "low",
      text: "测试",
      created_at: "2026-07-31T09:00:00Z",
      expires_at: "2026-07-31T09:00:08Z",
      personality_version: 7,
      style: "restrained",
      assistant_name: "PA",
      evidence: "manual-test",
    });
    expect(await screen.findByText("event-42")).toBeInTheDocument();
    expect(screen.getByText("后端已接受")).toBeInTheDocument();
    expect(screen.queryByText(/已投递/)).not.toBeInTheDocument();
  });
});


describe("Token precedence", () => {
  it("prefers window.PA_TOKEN over the session token", () => {
    sessionStorage.setItem("pa-api-token", "session-token");
    window.PA_TOKEN = "injected-token";
    expect(getApiToken()).toBe("injected-token");
  });
});
describe("Connection token", () => {
  it("stores the token only in sessionStorage and verifies authenticated endpoints", async () => {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", segments: 2, memories: 3 });
    vi.spyOn(api, "assistantPersonality").mockResolvedValue(personality);
    render(<ConnectionPage />);

    fireEvent.change(screen.getByLabelText("PA API Token"), { target: { value: "session-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "保存并验证" }));

    await screen.findByText("连接与鉴权均正常");
    expect(sessionStorage.getItem("pa-api-token")).toBe("session-secret");
    expect(getApiToken()).toBe("session-secret");
    expect(localStorage.getItem("pa-api-token")).toBeNull();
  });

  it("does not retain a newly submitted invalid token", async () => {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", segments: 2, memories: 3 });
    vi.spyOn(api, "assistantPersonality").mockRejectedValue(
      new ApiError("Forbidden", 403, "/assistant/personality", { detail: "Forbidden" }),
    );
    render(<ConnectionPage />);

    fireEvent.change(screen.getByLabelText("PA API Token"), { target: { value: "invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "保存并验证" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Token 无效或已过期");
    expect(sessionStorage.getItem("pa-api-token")).toBeNull();
  });

  it("shows a clear authentication error and can clear the session token", async () => {
    sessionStorage.setItem("pa-api-token", "expired");
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", segments: 2, memories: 3 });
    vi.spyOn(api, "assistantPersonality").mockRejectedValue(
      new ApiError("Unauthorized", 401, "/assistant/personality", { detail: "Unauthorized" }),
    );
    render(<ConnectionPage />);

    fireEvent.click(screen.getByRole("button", { name: "验证连接" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Token 无效或已过期");
    fireEvent.click(screen.getByRole("button", { name: "清除 Token" }));
    expect(sessionStorage.getItem("pa-api-token")).toBeNull();
  });
});

describe("Sidebar navigation", () => {
  it("uses the exact route groups without deleted destinations", async () => {
    render(<Sidebar />);

    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assistant" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Life" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /对话|人格|运行/ })).not.toBeInTheDocument();
  });
});
