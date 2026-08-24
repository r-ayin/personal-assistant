import type {
  AssistantPersonality,
  AssistantPersonalityInput,
  AssistantPersonalitySaveInput,
  BarrageEvent,
  BarrageSettings,
  BarrageStatus,
  ChatLog,
  Event,
  LLMConfig,
  Memory,
  PerceptionStatus,
  PersonalityPreview,
  ProfileFeedbackInput,
  ProfileResponse,
  Reminder,
  RuntimeStatus,
  Segment,
  Speaker,
  WikiPage,
} from "./types";

declare global {
  interface Window {
    PA_BASE?: string;
    PA_TOKEN?: string;
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly path: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getApiBase(): string {
  return typeof window !== "undefined" ? window.PA_BASE || "" : "";
}

export function getApiToken(): string {
  if (typeof window === "undefined") return "";
  return window.PA_TOKEN || window.sessionStorage.getItem("pa-api-token") || "";
}

export function setApiToken(token: string): void {
  if (typeof window === "undefined") return;
  const value = token.trim();
  if (value) window.sessionStorage.setItem("pa-api-token", value);
  else window.sessionStorage.removeItem("pa-api-token");
}

export function clearApiToken(): void {
  if (typeof window !== "undefined") window.sessionStorage.removeItem("pa-api-token");
}

function headers(token = getApiToken()): Record<string, string> {
  const value: Record<string, string> = { Accept: "application/json" };
  if (token) value.Authorization = `Bearer ${token}`;
  return value;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(getApiBase() + path, {
      ...init,
      headers: { ...headers(), ...init.headers },
    });
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : "无法连接 PA 后端",
      0,
      path,
    );
  }
  if (!response.ok) {
    let details: unknown;
    let detail = `${response.status} ${response.statusText}`.trim();
    try {
      details = await response.json();
      if (typeof details === "object" && details !== null && "detail" in details) {
        const value = details.detail;
        if (typeof value === "string") detail = value;
      }
    } catch {
      // The HTTP status remains the useful error when the body is not JSON.
    }
    throw new ApiError(detail, response.status, path, details);
  }
  return (await response.json()) as T;
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T | null> {
  try {
    const query = params ? `?${new URLSearchParams(params)}` : "";
    return await request<T>(path + query);
  } catch {
    return null;
  }
}

async function post<T>(path: string, body?: unknown): Promise<T | null> {
  try {
    return await request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
  } catch {
    return null;
  }
}

function requiredGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const query = params ? `?${new URLSearchParams(params)}` : "";
  return request<T>(path + query);
}

function requiredPost<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function requiredPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function requiredDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

export const api = {
  health: () => requiredGet<{ status: string; segments: number; memories: number }>("/health"),
  chat: (message: string, conversationId?: string) =>
    requiredPost<{ reply: string; evidence: string[]; conversation_id?: string | null }>(
      "/chat",
      conversationId ? { message, conversation_id: conversationId } : { message },
    ),
  chatLog: (limit = "50") => requiredGet<{ chat_log: ChatLog[] }>("/chat-log", { limit }),
  events: (day?: string) => requiredGet<{ events: Event[] }>("/events", day ? { day } : undefined),
  reminders: () => requiredGet<{ reminders: Reminder[] }>("/reminders"),
  localModelStatus: () => requiredGet<RuntimeStatus>("/local-model/status"),
  startLocalModel: () => requiredPost<RuntimeStatus>("/local-model/start"),
  stopLocalModel: () => requiredPost<RuntimeStatus>("/local-model/stop"),
  startPerception: () => requiredPost<PerceptionStatus>("/perception/start"),
  stopPerception: () => requiredPost<PerceptionStatus>("/perception/stop"),
  barrageSettings: () => requiredGet<BarrageSettings>("/barrage/settings"),
  updateBarrageSettings: (body: Partial<BarrageSettings>) =>
    requiredPut<BarrageSettings>("/barrage/settings", body),
  barrageStatus: () => requiredGet<BarrageStatus>("/barrage/status"),
  testBarrage: () => requiredPost<BarrageEvent>("/barrage/test"),
  assistantPersonality: () => requiredGet<AssistantPersonality>("/assistant/personality"),
  previewAssistantPersonality: (body: AssistantPersonalityInput) =>
    requiredPost<PersonalityPreview>("/assistant/personality/preview", body),
  updateAssistantPersonality: (body: AssistantPersonalitySaveInput) =>
    requiredPut<AssistantPersonality>("/assistant/personality", body),
  profile: () => requiredGet<ProfileResponse>("/profile"),
  addProfileFeedback: (body: ProfileFeedbackInput) =>
    requiredPost<{ id: string; active: true }>("/profile/feedback", body),
  deleteProfileFeedback: (feedbackId: string) =>
    requiredDelete<{ id: string; active: false }>(`/profile/feedback/${encodeURIComponent(feedbackId)}`),

  segments: (limit = "50", offset = "0") => get<{ segments: Segment[]; total: number }>("/segments", { limit, offset }),
  memories: () => get<{ memories: Memory[] }>("/memories"),
  distill: () => post<unknown>("/distill"),
  calendar: (q: string) => get<{ events: Event[]; query: string }>("/calendar", { q }),
  remindersCheck: () => post<unknown>("/reminders/check"),
  speakers: () => get<{ speakers: Speaker[] }>("/speakers"),
  verify: () => post<unknown>("/verify"),
  recommend: (kind = "book", query = "") => post<{ recommendations: unknown[] }>("/recommend", { kind, query }),
  wiki: (q = "") => get<{ pages?: WikiPage[]; topics?: unknown[] }>("/wiki", { q }),
  wikiBuild: () => post<unknown>("/wiki/build"),
  ingest: () => post<unknown>("/ingest"),
  triggers: () => post<unknown>("/triggers"),
  proactive: () => post<unknown>("/proactive"),
  llmSettings: () => requiredGet<LLMConfig>("/settings/llm"),
  updateLLM: (body: Partial<LLMConfig>) => requiredPost<LLMConfig>("/settings/llm", body),
  uploadInbox: async (filename: string, content: ArrayBuffer) => {
    try {
      return await request<unknown>(`/inbox/upload?filename=${encodeURIComponent(filename)}`, {
        method: "POST",
        body: content,
      });
    } catch {
      return null;
    }
  },
};

export type {
  AssistantPersonality,
  BarrageSettings,
  ChatLog,
  Event,
  LLMConfig,
  Memory,
  Reminder,
  RuntimeStatus,
  Segment,
  Speaker,
  WikiPage,
};
