package com.personalassistant.data.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

// ── DTO：严格对齐 api.py 真实返回 shape（反幻觉字段一路透传，不丢不重命名）──

@Serializable
data class HealthOut(
    val status: String? = null,
    val llm: String? = null,
    val asr: String? = null,
    val embedder: String? = null,
    val speaker: String? = null,
)

@Serializable
data class Segment(
    val id: String,
    val source_file: String? = null,
    val start_sec: Double? = null,
    val end_sec: Double? = null,
    val text: String? = null,
    val speaker: String? = null,
    val language: String? = null,
    val created_at: String? = null,
    val processed: Int? = null,
    val time_kind: String? = null,
)

@Serializable
data class SegmentsOut(val count: Int = 0, val segments: List<Segment> = emptyList())

@Serializable
data class Memory(
    val id: String,
    val segment_id: String? = null,
    val kind: String? = null,
    val content: String? = null,
    val evidence: String? = null,          // 溯源（SourceChip 依据）
    val created_at: String? = null,
    val processed: Int? = null,
)

@Serializable
data class MemoriesOut(val count: Int = 0, val memories: List<Memory> = emptyList())

@Serializable
data class ProfileOut(
    val version: Int? = null,
    val change_summary: String? = null,
    val profile: Map<String, String> = emptyMap(),   // 扁平 9 维文本（不捏造 score）
)

@Serializable
data class ChatIn(val message: String)

@Serializable
data class ChatOut(val reply: String = "")

@Serializable
data class ChatLogEntry(val role: String? = null, val content: String? = null, val created_at: String? = null)

@Serializable
data class ChatLogOut(val logs: List<ChatLogEntry> = emptyList())

@Serializable
data class VerifyOut(
    val assertion: String? = null,        // "passed" / "failed: ..."
    // rep 其余字段（kept/deleted 计数等）保留为 JsonObject，不丢
    val others: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class TriggersOut(val fired: List<String> = emptyList())

@Serializable
data class Event(
    val id: String? = null,
    val title: String? = null,
    val when_dt: String? = null,          // 确定性解析绝对日期（temporal，绿）
    val when_raw: String? = null,         // LLM 抽取原文（金）
    val who: String? = null,
    val where: String? = null,
    val source_segment: String? = null,
    val created_at: String? = null,
)

@Serializable
data class CalendarOut(val count: Int = 0, val events: List<Event> = emptyList())

@Serializable
data class EventsOut(val events: List<Event> = emptyList())

@Serializable
data class Reminder(
    val id: String? = null,
    val what: String? = null,
    val when_dt: String? = null,
    val when_raw: String? = null,
    val recurring: String? = null,
    val source_segment: String? = null,
    val fired: Int? = null,
    val created_at: String? = null,
)

@Serializable
data class RemindersOut(val reminders: List<Reminder> = emptyList())

@Serializable
data class RemindersCheckOut(val fired: List<String> = emptyList())

@Serializable
data class Speaker(val name: String? = null, val label: String? = null, val note: String? = null, val created_at: String? = null)

@Serializable
data class SpeakersOut(val speakers: List<Speaker> = emptyList())

@Serializable
data class Recommendation(val item: String? = null, val reason: String? = null, val based_on: String? = null)

@Serializable
data class RecommendOut(val count: Int = 0, val recommendations: List<Recommendation> = emptyList())

@Serializable
data class WikiPage(
    val id: String? = null,
    val title: String? = null,
    val body: String? = null,
    val tags: List<String> = emptyList(),
    val source_ids: List<String> = emptyList(),   // 链式溯源 → 记忆 id
    val link_ids: List<String> = emptyList(),
    val created_at: String? = null,
)

@Serializable
data class WikiOut(val pages: List<WikiPage> = emptyList())

@Serializable
data class WikiBuildOut(val built: JsonElement? = null)

// ── LLM 配置（诚实配置：key 掩码不回显，native_preview 展示 provider 原生字段）──

@Serializable
data class LlmSettings(
    val backend: String = "stub",
    val model: String? = null,
    val base_url: String? = null,
    val api_key_masked: String? = null,           // 永不持有明文 key
    val max_tokens: Int? = null,
    val thinking_effort: String? = null,          // off·低·中·高
    val thinking_format: String? = null,          // glm·openai·qwen·anthropic
    val native_preview: JsonElement? = null,      // 后端算好的原生字段，App 不捏造 budget
    val uses_max_completion_tokens: Boolean? = null,
)

@Serializable
data class LlmSettingsIn(
    val backend: String? = null,
    val model: String? = null,
    val context_window: Int? = null,              // 仅 POST 入参，GET 不回显
    val max_tokens: Int? = null,
    val thinking_effort: String? = null,
    val thinking_format: String? = null,
    val base_url: String? = null,
    val api_key: String? = null,                  // 直接发往后端，本地不缓存
)

@Serializable
data class LlmSettingsUpdateOut(
    val backend: String? = null,
    val applied: List<String> = emptyList(),
    val effective: LlmSettings? = null,
    val note: String? = null,
)

@Serializable
data class InboxUploadOut(val saved: String? = null, val bytes: Int? = null, val ingest_hint: String? = null)
