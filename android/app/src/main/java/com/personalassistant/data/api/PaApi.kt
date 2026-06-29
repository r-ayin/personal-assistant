package com.personalassistant.data.api

import com.personalassistant.data.model.*
import kotlinx.serialization.json.JsonObject
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.http.Streaming

/**
 * Retrofit 接口，严格对齐 api.py 21 端点。
 * ingest / verify / distill 返回结构较松的 dict，统一用 JsonObject，由 PaRepository 取字段。
 * `/inbox/upload`：原始 body + ?filename= 查询参数，**免 multipart**（dev 盒 python-multipart 缺）。
 */
interface PaApi {

    @GET("health")
    suspend fun health(): HealthOut

    @POST("ingest")
    suspend fun ingest(): JsonObject

    @GET("segments")
    suspend fun segments(): SegmentsOut

    @GET("memories")
    suspend fun memories(): MemoriesOut

    @GET("profile")
    suspend fun profile(): ProfileOut

    @POST("chat")
    suspend fun chat(@Body body: ChatIn): ChatOut

    @GET("chat-log")
    suspend fun chatLog(): ChatLogOut

    @POST("verify")
    suspend fun verify(): JsonObject

    @POST("distill")
    suspend fun distill(): JsonObject

    @POST("triggers")
    suspend fun triggers(): TriggersOut

    @GET("calendar")
    suspend fun calendar(@Query("q") q: String): CalendarOut

    @GET("events")
    suspend fun events(): EventsOut

    @GET("reminders")
    suspend fun reminders(): RemindersOut

    @POST("reminders/check")
    suspend fun remindersCheck(): RemindersCheckOut

    @GET("speakers")
    suspend fun speakers(): SpeakersOut

    @GET("recommend")
    suspend fun recommend(@Query("kind") kind: String, @Query("q") q: String): RecommendOut

    @GET("wiki")
    suspend fun wiki(@Query("tag") tag: String, @Query("q") q: String): WikiOut

    @POST("wiki/build")
    suspend fun wikiBuild(): WikiBuildOut

    @GET("settings/llm")
    suspend fun llmSettings(): LlmSettings

    @POST("settings/llm")
    suspend fun updateLlm(@Body body: LlmSettingsIn): LlmSettingsUpdateOut

    /** 原始 body + filename 查询，免 multipart。Content-Type 由调用方设（text/plain）。 */
    @Streaming
    @POST("inbox/upload")
    suspend fun uploadInbox(
        @Body body: RequestBody,
        @Query("filename") filename: String,
    ): InboxUploadOut
}
