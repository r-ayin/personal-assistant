package com.personalassistant.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "pa_settings")

/**
 * App 本地仅持 BASE_URL + 可选鉴权 token（加密存储留 EncryptedDataStore 扩展）。
 * 隐私硬约束（设计稿§0.2/§1.3）：API key 永不出现在 App；此处不存任何 LLM key。
 */
class AppConfig(private val ctx: Context) {
    private val KEY_BASE_URL = stringPreferencesKey("base_url")
    private val KEY_AUTH_TOKEN = stringPreferencesKey("auth_token")

    val baseUrl: Flow<String> = ctx.dataStore.data.map { it[KEY_BASE_URL] ?: DEFAULT_BASE_URL }
    val authToken: Flow<String> = ctx.dataStore.data.map { it[KEY_AUTH_TOKEN] ?: "" }

    suspend fun setBaseUrl(url: String) = ctx.dataStore.edit { it[KEY_BASE_URL] = url.trimEnd('/') }
    suspend fun setAuthToken(token: String) = ctx.dataStore.edit { it[KEY_AUTH_TOKEN] = token }

    companion object {
        // 默认指向同网段大脑；用户在设置页改成实际 BASE_URL（如 http://192.168.x.x:8000）
        const val DEFAULT_BASE_URL = "http://localhost:8000"
    }
}
