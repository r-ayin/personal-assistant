// Mock 数据 — 全空占位，由 bootstrap() 从后端填充
const MockData = (() => {
  const segments = [];
  const memories = [];
  const events = [];
  const reminders = [];
  const chatLog = [];
  const speakers = [];
  const persona = { version: 0, change_summary: "", profile: {}, versions: [] };
  const interventions = [];
  const recommendations = { book: [], movie: [], action: [] };
  const wikiPages = [];
  const verifyReport = { status: "passed", passed: 0, failed: 0, warned: 0, total: 0, items: [] };
  const health = { api: "loading", llm: "—", asr: "—", embedder: "—", speaker: "—", db: "—", latency_ms: 0 };
  const agents = [];

  return { segments, memories, events, reminders, chatLog, speakers, persona, interventions, recommendations, wikiPages, verifyReport, health, agents };
})();

Object.assign(window, { MockData });
