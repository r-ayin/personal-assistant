import { getApiBase, getApiToken } from "./api";
import type { LiveEvent } from "./types";

export interface LiveState {
  connected: boolean;
  lastError: string;
}

type LiveListener = (event: LiveEvent) => void;
type StateListener = (state: LiveState) => void;

const RETRY_DELAYS = [1000, 2000, 5000, 10000, 30000] as const;

function socketBase(httpBase: string): string {
  if (httpBase) return httpBase.replace(/^http/, "ws").replace(/\/$/, "");
  if (typeof window === "undefined") return "";
  return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
}

export class LiveClient {
  private socket: WebSocket | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryIndex = 0;
  private stopped = true;
  private listeners = new Set<LiveListener>();
  private stateListeners = new Set<StateListener>();
  private state: LiveState = { connected: false, lastError: "" };

  connect(): void {
    this.stopped = false;
    this.open();
  }

  disconnect(): void {
    this.stopped = true;
    clearTimeout(this.retryTimer ?? undefined);
    this.retryTimer = null;
    this.socket?.close();
    this.socket = null;
    this.updateState({ connected: false, lastError: "" });
  }

  subscribe(listener: LiveListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  subscribeState(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => this.stateListeners.delete(listener);
  }

  getState(): LiveState {
    return this.state;
  }

  private open(): void {
    if (this.stopped || typeof WebSocket === "undefined") return;
    const token = getApiToken();
    const url = `${socketBase(getApiBase())}/ws/live?client=page&version=1&token=${encodeURIComponent(token)}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      if (socket !== this.socket) return;
      this.retryIndex = 0;
      this.updateState({ connected: true, lastError: "" });
    };
    socket.onmessage = (message) => {
      if (socket !== this.socket) return;
      try {
        const event = JSON.parse(String(message.data)) as LiveEvent;
        if (event.type === "barrage") return;
        this.listeners.forEach((listener) => listener(event));
      } catch {
        this.updateState({ connected: true, lastError: "实时消息格式无效" });
      }
    };
    socket.onerror = () => {
      if (socket === this.socket) {
        this.updateState({ connected: false, lastError: "实时连接失败" });
      }
    };
    socket.onclose = () => {
      if (socket !== this.socket) return;
      this.socket = null;
      if (this.stopped) return;
      this.updateState({ connected: false, lastError: "实时连接已断开" });
      const delay = RETRY_DELAYS[Math.min(this.retryIndex, RETRY_DELAYS.length - 1)];
      this.retryIndex = Math.min(this.retryIndex + 1, RETRY_DELAYS.length - 1);
      this.retryTimer = setTimeout(() => this.open(), delay);
    };
  }

  private updateState(state: LiveState): void {
    this.state = state;
    this.stateListeners.forEach((listener) => listener(state));
  }
}

export const liveClient = new LiveClient();
