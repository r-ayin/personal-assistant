// 显示层中文映射 —— 数据层保留稳定英文键，页面展示统一译成中文。
// 新增英文键时在此补充映射即可，未映射的键原样回退。

/** 时刻标签（moment tags）：wish/vulnerability/gratitude/regret/love/courage */
export const MOMENT_TAG_LABELS: Record<string, string> = {
  wish: "心愿",
  vulnerability: "脆弱",
  gratitude: "感激",
  regret: "遗憾",
  love: "爱",
  courage: "勇气",
};

export function momentTagLabel(tag: string): string {
  const t = (tag || "").trim();
  return MOMENT_TAG_LABELS[t] || MOMENT_TAG_LABELS[t.toLowerCase()] || t;
}

export function momentTagLabels(tags?: string[]): string {
  return (tags || []).map(momentTagLabel).join(" · ");
}

/** 记忆知识层 kind：fact/skill/knowledge/preference/intention/emotion/moment */
export const MEMORY_KIND_LABELS: Record<string, string> = {
  fact: "事实",
  skill: "技能",
  knowledge: "知识",
  preference: "偏好",
  intention: "意图",
  emotion: "情绪",
  moment: "时刻",
};

export function memoryKindLabel(kind: string): string {
  return MEMORY_KIND_LABELS[kind] || MEMORY_KIND_LABELS[(kind || "").toLowerCase()] || kind;
}

/** 助手人格预设：gentle/rational/lively/coach/custom */
export const PRESET_LABELS: Record<string, string> = {
  gentle: "温柔",
  rational: "理性",
  lively: "活泼",
  coach: "教练",
  custom: "自定义",
};

/** 主动性：quiet/restrained/balanced/active/companion */
export const INITIATIVE_LABELS: Record<string, string> = {
  quiet: "安静",
  restrained: "克制",
  balanced: "均衡",
  active: "主动",
  companion: "陪伴",
};

/** 回复长度：short/balanced/detailed */
export const REPLY_LENGTH_LABELS: Record<string, string> = {
  short: "简短",
  balanced: "适中",
  detailed: "详尽",
};

export function pick(map: Record<string, string>, key?: string): string {
  const k = (key || "").trim();
  return map[k] || map[k.toLowerCase()] || k;
}

/** 文本级翻译：后端字符串值里内嵌的英文标签（如情感基线 "vulnerability, wish"）逐词替换为中文 */
export function localizeDisplayText(text: string): string {
  if (!text) return text;
  let out = text;
  for (const [en, zh] of Object.entries(MOMENT_TAG_LABELS)) {
    out = out.replace(new RegExp(`\\b${en}\\b`, "gi"), zh);
  }
  return out;
}

/** 提醒循环周期：daily/weekly/monthly/yearly（自由字符串，未命中原样回退） */
export const RECURRING_LABELS: Record<string, string> = {
  daily: "每日",
  weekly: "每周",
  monthly: "每月",
  yearly: "每年",
  once: "单次",
  weekdays: "工作日",
};

/** 校验结果 key 映射：events_kept/events_deleted/… */
export const VERIFY_LABELS: Record<string, string> = {
  events_kept: "保留事件",
  events_deleted: "删除事件",
  reminders_kept: "保留提醒",
  reminders_deleted: "删除提醒",
  memories_kept: "保留记忆",
  memories_deleted: "删除记忆",
};

/** 时刻对话场景：dm/group/official/openim/doc */
export const CHAT_KIND_LABELS: Record<string, string> = {
  dm: "单聊",
  group: "群聊",
  official: "公众号",
  openim: "企业号",
  doc: "文档",
};

export function chatKindLabel(kind?: string): string {
  return pick(CHAT_KIND_LABELS, kind || "");
}

/** LLM 后端：stub/ollama/openai_compat/anthropic_proxy/deepseek/deepseek_anthropic/glm_anthropic */
export const LLM_BACKEND_LABELS: Record<string, string> = {
  stub: "占位（不联网）",
  ollama: "本地 Ollama",
  openai_compat: "OpenAI 兼容",
  anthropic_proxy: "Anthropic 代理",
  deepseek: "DeepSeek",
  deepseek_anthropic: "DeepSeek（Anthropic 协议）",
  glm_anthropic: "智谱（Anthropic 协议）",
};

export function llmBackendLabel(backend?: string): string {
  return pick(LLM_BACKEND_LABELS, backend || "");
}

/** 召回策略：hybrid/vector/fts/keyword/bm25/fallback */
export const RECALL_STRATEGY_LABELS: Record<string, string> = {
  hybrid: "混合召回",
  vector: "向量召回",
  fts: "全文检索",
  keyword: "关键词召回",
  bm25: "关键词召回",
  fallback: "兜底召回",
};

export function recallStrategyLabel(strategy?: string): string {
  return pick(RECALL_STRATEGY_LABELS, strategy || "");
}

/** 说话人：设备主人在展示层叫「我」，其余名字原样 */
export function speakerLabel(name?: string): string {
  const n = (name || "").trim();
  return n.toLowerCase() === "user" ? "我" : n;
}
