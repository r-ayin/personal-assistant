package com.personalassistant.data

import com.personalassistant.data.api.PaApi
import com.personalassistant.data.model.*
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive

/**
 * 仓库：聚合 [PaApi]，统一 Result 风格返回，离线降级留 Room 缓存扩展（Phase 2）。
 * 反幻觉字段（evidence/source_ids/time_kind/when_raw/when_dt/native_preview）一路透传到 UiState。
 */
class PaRepository(private val client: PaClient) {

    private fun api(): PaApi = client.api()

    suspend fun health(): Result<HealthOut> = runCatching { api().health() }
    suspend fun ingest(): Result<JsonObject> = runCatching { api().ingest() }
    suspend fun segments(): Result<SegmentsOut> = runCatching { api().segments() }
    suspend fun memories(): Result<MemoriesOut> = runCatching { api().memories() }
    suspend fun profile(): Result<ProfileOut> = runCatching { api().profile() }
    suspend fun chat(message: String): Result<ChatOut> = runCatching { api().chat(ChatIn(message)) }
    suspend fun chatLog(): Result<ChatLogOut> = runCatching { api().chatLog() }

    /** /verify 返回 rep + assertion；提取 assertion 串 + 整 rep。 */
    suspend fun verify(): Result<Pair<String?, JsonObject>> = runCatching {
        val rep = api().verify()
        val assertion = rep["assertion"]?.jsonPrimitive?.content
        assertion to rep
    }

    suspend fun distill(): Result<JsonObject> = runCatching { api().distill() }
    suspend fun triggers(): Result<TriggersOut> = runCatching { api().triggers() }
    suspend fun calendar(q: String): Result<CalendarOut> = runCatching { api().calendar(q) }
    suspend fun events(): Result<EventsOut> = runCatching { api().events() }
    suspend fun reminders(): Result<RemindersOut> = runCatching { api().reminders() }
    suspend fun remindersCheck(): Result<RemindersCheckOut> = runCatching { api().remindersCheck() }
    suspend fun speakers(): Result<SpeakersOut> = runCatching { api().speakers() }
    suspend fun recommend(kind: String, q: String): Result<RecommendOut> = runCatching { api().recommend(kind, q) }
    suspend fun wiki(tag: String, q: String): Result<WikiOut> = runCatching { api().wiki(tag, q) }
    suspend fun wikiBuild(): Result<WikiBuildOut> = runCatching { api().wikiBuild() }
    suspend fun llmSettings(): Result<LlmSettings> = runCatching { api().llmSettings() }
    suspend fun updateLlm(inp: LlmSettingsIn): Result<LlmSettingsUpdateOut> = runCatching { api().updateLlm(inp) }

    /** 投递转录文本到 inbox（免 multipart）。 */
    suspend fun uploadTranscript(filename: String, text: String): Result<InboxUploadOut> =
        runCatching { api().uploadInbox(client.textBody(text), filename) }
}
