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
export type PersonalityBarrageStyle = "restrained" | "light" | "coach" | "game";

export interface AssistantPersonalityInput {
  preset_id: PersonalityPreset | "custom";
  name: string;
  user_address: string;
  directness: number;
  humor: number;
  initiative: PersonalityInitiative;
  reply_length: PersonalityReplyLength;
  barrage_style: PersonalityBarrageStyle;
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

export interface RuntimeStatus {
  state: string;
  running: boolean;
  error: string;
  consumers: string[];
  model?: string;
  device?: string;
}

export interface BarrageSettings {
  enabled: boolean;
  quiet_mode: boolean;
  paused_until: string;
  position: "top" | "center" | "bottom";
  font_size: number;
  opacity: number;
  duration_seconds: number;
  theme: "contrast" | "light" | "dark";
  display_id: string;
}

export interface BarrageStatus {
  settings: BarrageSettings;
  overlay_clients: number;
  paused: boolean;
}

export interface PerceptionStatus {
  perception: "running" | "stopped" | string;
  local_model: RuntimeStatus;
}

export interface BarrageEvent {
  id: string;
  kind: string;
  priority: "high" | "medium" | "low";
  text: string;
  created_at: string;
  expires_at: string;
  personality_version: number;
  style: string;
  assistant_name: string;
  evidence: string;
}

export interface LiveEvent<T = Record<string, unknown>> {
  type: string;
  data: T;
  ts: string;
}
