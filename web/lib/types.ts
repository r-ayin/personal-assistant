export interface Segment {
  id: string;
  source_file: string;
  start_sec: number;
  end_sec: number;
  text: string;
  speaker: string;
  language: string;
  created_at: string;
  processed: number;
  time_kind: "received" | "occurred";
}

export interface Memory {
  id: string;
  segment_id: string;
  kind: string;
  content: string;
  evidence: string;
  created_at: string;
  processed: number;
}

export interface Moment {
  id: number;
  verbatim_quote: string;
  narrative: string;
  tags: string[];
  speaker: string;
  timestamp: string;
  recalled?: number;
  created_at?: string;
  source_file?: string;
  // 人物层（2026-08-31）：时刻锚定到具体的人与关系
  counterpart?: string;        // 对话对象（单聊对方/群名）
  chat_kind?: string;          // dm | group | official | openim | doc
  about_person?: string;       // 时刻关乎的人（可为"自己"）
  relationship_signal?: string; // 关系信号（一句话）
}

export interface Event {
  id: string;
  title: string;
  when_dt: string;
  when_raw: string;
  who: string;
  where: string;
  source_segment: string;
  created_at: string;
}

export interface Reminder {
  id: string;
  what: string;
  when_dt: string;
  when_raw: string;
  recurring: string;
  source_segment: string;
  fired: number;
  created_at: string;
}

export interface ChatLog {
  id: number | string;
  role: "user" | "assistant" | string;
  content: string;
  evidence?: string[] | string;
  created_at: string;
}

export interface WikiPage {
  id: string;
  title: string;
  body: string;
  tags: string;
  source_ids: string;
  link_ids: string;
  created_at: string;
}

export interface Speaker {
  name: string;
  label: string;
  note: string;
  created_at: string;
}

export type ProfileDimension =
  | "personality"
  | "values"
  | "goals"
  | "habits"
  | "skills"
  | "knowledge"
  | "thinking_patterns"
  | "preferences"
  | "affective_baseline";

export type ProfileValue = string | string[] | number | boolean | null;

export interface ProfileFeedback {
  id: string;
  dimension: ProfileDimension;
  value: string;
  action: "add" | "suppress";
  evidence_kind: "user_statement";
  evidence: string;
  active: boolean;
  created_at: string;
  deactivated_at?: string;
}

export interface ProfileFeedbackInput {
  dimension: ProfileDimension;
  value: string;
  action: "add" | "suppress";
  evidence_kind: "user_statement";
  evidence: string;
}

export interface ProfileResponse {
  inferred: Partial<Record<ProfileDimension, ProfileValue>>;
  effective: Partial<Record<ProfileDimension, ProfileValue>>;
  version: number;
  change_summary: string;
  feedback: ProfileFeedback[];
}

export interface LLMConfig {
  backend: string;
  model?: string;
  base_url?: string;
  api_key_masked?: string;
  max_tokens?: number;
  thinking_effort?: string;
  thinking_format?: string;
  native_preview?: Record<string, unknown>;
  uses_max_completion_tokens?: boolean;
}

export type PersonalityPreset = "gentle" | "rational" | "lively" | "coach";
export type PersonalityInitiative = "quiet" | "restrained" | "balanced" | "active" | "companion";
export type PersonalityReplyLength = "short" | "balanced" | "detailed";
export type BarrageStyle = "restrained" | "light" | "coach" | "game";

export interface AssistantPersonalityInput {
  preset_id: PersonalityPreset | "custom";
  name: string;
  user_address: string;
  directness: number;
  humor: number;
  initiative: PersonalityInitiative;
  reply_length: PersonalityReplyLength;
  barrage_style: BarrageStyle;
  taboos: string[];
  custom_instruction: string;
}

export interface AssistantPersonality extends AssistantPersonalityInput {
  version: number;
  created_at: string;
}

export interface AssistantPersonalitySaveInput extends AssistantPersonalityInput {
  expected_version: number;
}

export interface PersonalityPreview {
  chat: string;
  reminder: string;
  perception: string;
}

/** GET /status —— 全局计数 */
export interface StatusPayload {
  segments: number;
  memories: number;
  events: number;
  reminders: number;
  speakers: number;
  profile_version: number;
}

/** GET /memories/recall —— 混合召回单条命中 */
export interface RecallItem {
  id: string;
  kind: string;
  content: string;
  priority: number;
  score: number;
  sources: string[];
}

export interface RecallResponse {
  items: RecallItem[];
  truncated: boolean;
  elapsed_ms: number;
  strategy: string;
}

/** GET /verify —— 校验六键（展示经 labels.ts VERIFY_LABELS 翻译） */
export interface VerifyReport {
  events_kept: number;
  events_deleted: number;
  reminders_kept: number;
  reminders_deleted: number;
  memories_kept: number;
  memories_deleted: number;
}

/** POST /recommend —— 单条推荐（LLM 输出，键宽松） */
export interface Recommendation {
  item: string;
  reason?: string;
  based_on?: string[];
  [key: string]: unknown;
}

/* ════════════════════════════════════════════════════════════
   画像层（2026-09-01 追加）—— GET /portrait/* 与 /memory/search。
   后端只读 memory.db；库不存在时返回 {available:false}，UI 必须优雅降级。
   行结构直接映射 SQLite 列，JSON 列（dist/tags/score_history 等）仍是字符串，
   由展示层解析——解析失败一律回退"不可解析"，绝不编造数值。
   ════════════════════════════════════════════════════════════ */

/** person 表整行 */
export interface PortraitPersonRow {
  person_id: string;
  person_kind: string; // self|person|official|bot|unknown
  display_name: string;
  profile_card: string; // Letta 式 memory block（markdown 文本）
  role: string;
  created_at?: string;
  updated_at?: string;
}

/** trait 表投影行；dist 是 JSON 字符串 {mean,sd,skew,n_observations,last_updated} */
export interface PortraitTrait {
  dimension: string;
  dist: string;
  promoted: number; // 0/1：≥3 独立会话复现才升格
  n_independent_conv: number;
  is_proxy: number; // 0/1：行为代理推断，非量表实测
}

/** dist JSON 解析后的形状 */
export interface TraitDist {
  mean?: number;
  sd?: number;
  skew?: number;
  n_observations?: number;
  last_updated?: string;
}

/** goal 表整行（节选常用列，其余透传） */
export interface PortraitGoal {
  id: number;
  subject_id?: string;
  text_gist: string;
  level: string; // runway|project|area|goal_1_2y|vision_3_5y|purpose
  domain?: string;
  status: string;
  deadline?: string;
  specificity?: number | null;
  difficulty?: number | null;
  progress_pct?: number | null;
  commitment_evidence_count?: number;
  possible_self_type?: string;
  first_seen_at?: string;
  last_active_at?: string;
}

/** task 表整行（GTD 类型） */
export interface PortraitTask {
  id: number;
  raw_text: string;
  normalized_verb_object?: string;
  type: string; // next_action|project|waiting_for|tickler|someday_maybe|reference
  trigger_type?: string;
  trigger_value?: string;
  due?: string;
  status: string; // inbox|clarified|active|blocked|done|dropped
  committed_to_whom?: string;
  zeigarnik_flag?: number;
  reopen_count?: number;
  created_at?: string;
  updated_at?: string;
}

/** value 表整行（Schwartz 价值观） */
export interface PortraitValue {
  id: number;
  statement: string;
  schwartz_domain: string;
  abstraction_level?: number;
  recurrence_count: number;
  confidence?: number;
  is_stable: number;
  first_ts?: string;
  last_ts?: string;
}

/** affect_profile 表整行 */
export interface PortraitAffect {
  id?: number;
  subject_id?: string;
  window: string;
  pa_mean: number | null;
  na_mean: number | null;
  variability_mssd: number | null;
  inertia: number | null;
  granularity: number | null;
  top_labels: string; // JSON 字符串
  n: number;
  eligible: number;
  ineligible_reason: string;
  computed_at?: string;
}

/** growth 表整行；score_history 是 JSON 字符串 [{window,proxy_score,evidence_count,...}] */
export interface PortraitGrowth {
  id: number;
  subject_id?: string;
  dimension: string; // autonomy|env_mastery|personal_growth|positive_relations|purpose|self_acceptance
  score_history: string;
  updated_at?: string;
}

/** GET /portrait/self */
export interface PortraitSelfResponse {
  available: boolean;
  person?: PortraitPersonRow | null;
  traits?: PortraitTrait[];
  goals?: PortraitGoal[];
  tasks?: PortraitTask[];
  values?: PortraitValue[];
  affect?: PortraitAffect[];
  growth?: PortraitGrowth[];
}

/** GET /portrait/circles 的人物聚合行 */
export interface CirclePerson {
  person_id: string;
  display_name: string;
  role: string;
  person_kind: string;
  profile_card: string;
  convs: number;
  msgs: number;
  user_msgs: number;
  first_ts: string | null;
  last_ts: string | null;
}

/** metric 表整行（复杂度指标层，eligible=1 必须带 n/CI/null_baseline） */
export interface PortraitMetricRow {
  subject_id: string;
  subject_kind: string; // self|person|conversation
  name: string;
  value: number | null;
  ci_low: number | null;
  ci_high: number | null;
  n: number | null;
  null_baseline?: string; // JSON 字符串
  params?: string; // JSON 字符串
  eligible: number;
  ineligible_reason: string;
  computed_at?: string;
}

/** GET /portrait/circles */
export interface PortraitCirclesResponse {
  available: boolean;
  people?: CirclePerson[];
  layers?: PortraitMetricRow[]; // dunbar_layers / signature_shares / social_entropy
}

/** person_alias 表投影行 */
export interface PersonAlias {
  label: string;
  alias_space: string; // wxid|nickname|remark|group_card|speaker_tag
  evidence_count: number;
  confidence: number;
}

/** GET /portrait/person 的 moment 投影行；tags 是 JSON 字符串 */
export interface PersonMoment {
  id: number;
  verbatim_quote: string;
  narrative: string;
  tags: string;
  ts: string;
  recalled: number;
}

/** GET /portrait/person 的 metric 投影行 */
export interface PersonMetric {
  name: string;
  value: number | null;
  ci_low: number | null;
  ci_high: number | null;
  n: number | null;
  eligible: number;
  ineligible_reason: string;
}

/** GET /portrait/person?id= */
export interface PortraitPersonResponse {
  available: boolean;
  person: PortraitPersonRow | null;
  aliases?: PersonAlias[];
  traits?: PortraitTrait[];
  values?: PortraitValue[];
  affect?: PortraitAffect[];
  moments?: PersonMoment[];
  metrics?: PersonMetric[];
}

/** GET /portrait/metrics */
export interface PortraitMetricsResponse {
  available: boolean;
  metrics?: PortraitMetricRow[];
}

/** GET /memory/search 单条命中（FTS5 bigram + 向量 + RRF + GA 终排） */
export interface MemorySearchHit {
  id: number;
  text: string;
  ts: string;
  person_id: string | null;
  conv_id: string | null;
  score: number;
  sources: string[]; // fts | vec
}

/** GET /memory/search */
export interface MemorySearchResponse {
  results: MemorySearchHit[];
}
