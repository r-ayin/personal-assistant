package com.personalassistant.data.model

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DTO 序列化往返测试：对齐 api.py 真实返回 shape，保证反幻觉字段一路透传不丢不重命名。
 * 纯 JVM（kotlinx.serialization 不依赖 Android 框架），junit runner，秒级。
 */
class DtosSerializationTest {

    private val json = Json {
        ignoreUnknownKeys = true   // api.py 返回可能带额外字段，忽略不炸
        encodeDefaults = true
    }

    @Test
    fun `HealthOut 字段往返`() {
        val src = HealthOut(status = "ok", llm = "glm", asr = "stub", embedder = "hashing")
        val s = json.encodeToString(HealthOut.serializer(), src)
        val back = json.decodeFromString(HealthOut.serializer(), s)
        assertEquals(src, back)
    }

    @Test
    fun `api 松散字段忽略未知键`() {
        // 后端可能新增字段，客户端不应因此崩溃
        val back = json.decodeFromString(
            HealthOut.serializer(),
            """{"status":"ok","future_field":"x","llm":"glm"}"""
        )
        assertEquals("ok", back.status)
        assertEquals("glm", back.llm)
    }

    @Test
    fun `Event 保留反幻觉字段 when_raw 与 when_dt`() {
        val src = Event(
            id = "e1",
            title = "周会",
            when_dt = "2026-07-01T10:00",      // 确定性解析绝对日期（绿）
            when_raw = "下周二上午十点",         // LLM 抽取原文（金）
            who = "我",
        )
        val s = json.encodeToString(Event.serializer(), src)
        assertTrue("when_raw 原文必须透传", s.contains("\"when_raw\":\"下周二上午十点\""))
        assertTrue("when_dt 绝对日期必须透传", s.contains("\"when_dt\":\"2026-07-01T10:00\""))
        val back = json.decodeFromString(Event.serializer(), s)
        assertEquals("下周二上午十点", back.when_raw)
        assertEquals("2026-07-01T10:00", back.when_dt)
    }

    @Test
    fun `Segment time_kind 透传 received 不冒充 occurred`() {
        val src = Segment(
            id = "s1",
            text = "你好",
            created_at = "2026-06-29T10:00",
            time_kind = "received",   // 记录时间，非真实发生时间
        )
        val back = json.decodeFromString(
            Segment.serializer(),
            json.encodeToString(Segment.serializer(), src)
        )
        assertEquals("received", back.time_kind)   // 不冒充 occurred
    }

    @Test
    fun `LlmSettings 永不回显明文 api_key`() {
        val src = LlmSettings(
            backend = "openai_compat",
            model = "glm-5.2",
            api_key_masked = "sk-***",   // 仅掩码，不持有明文
        )
        val s = json.encodeToString(LlmSettings.serializer(), src)
        assertFalse("明文 api_key 字段不应出现在 GET 回显中", s.contains("\"api_key\":"))
        assertTrue("应回显掩码 key", s.contains("\"api_key_masked\":\"sk-***\""))
    }

    @Test
    fun `Reminder 透传 when_raw 与 recurring`() {
        val src = Reminder(
            id = "r1",
            what = "吃药",
            when_raw = "每天早上八点",
            when_dt = "2026-06-30T08:00",
            recurring = "daily",
        )
        val back = json.decodeFromString(
            Reminder.serializer(),
            json.encodeToString(Reminder.serializer(), src)
        )
        assertEquals("每天早上八点", back.when_raw)
        assertEquals("daily", back.recurring)
    }
}
