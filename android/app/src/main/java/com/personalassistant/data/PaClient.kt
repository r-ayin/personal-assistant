package com.personalassistant.data

import com.personalassistant.data.api.PaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * 动态 BASE_URL 的 Retrofit 工厂：用户在设置页改 BASE_URL → [rebuild] → 下次 [api] 用新地址。
 * 鉴权 token（如有）以 Bearer 头注入；HTTPS 强烈建议，局域网可信例外。
 */
class PaClient(
    private val httpClient: OkHttpClient,
    val json: Json,
) {
    private val authClient: OkHttpClient = httpClient.newBuilder()
        .addInterceptor(AuthInterceptor { currentToken })
        .build()

    @Volatile private var currentBaseUrl: String = AppConfig.DEFAULT_BASE_URL
    @Volatile private var currentToken: String = ""
    @Volatile private var retrofit: Retrofit = buildRetrofit(currentBaseUrl)
    @Volatile private var apiRef: PaApi = retrofit.create(PaApi::class.java)

    /** 当前生效 BASE_URL（UI 展示）。 */
    val baseUrlFlow = MutableStateFlow(currentBaseUrl)

    fun api(): PaApi = apiRef

    fun rebuild(baseUrl: String, authToken: String) {
        val b = baseUrl.trimEnd('/')
        if (b == currentBaseUrl && authToken == currentToken) return
        currentBaseUrl = b
        currentToken = authToken
        retrofit = buildRetrofit(b)
        apiRef = retrofit.create(PaApi::class.java)
        baseUrlFlow.value = b
    }

    private fun buildRetrofit(baseUrl: String): Retrofit {
        val contentType = "application/json".toMediaTypeOrNull()!!
        return Retrofit.Builder()
            .baseUrl(if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
            .client(authClient)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
    }

    /** /inbox/upload 的原始 body（免 multipart）：转写文本 → text/plain RequestBody。 */
    fun textBody(text: String): RequestBody =
        text.toRequestBody("text/plain".toMediaTypeOrNull())
}

/** 注入鉴权头（如有 token）。 */
class AuthInterceptor(private val tokenProvider: () -> String) : okhttp3.Interceptor {
    override fun intercept(chain: okhttp3.Interceptor.Chain): Response {
        val t = tokenProvider()
        val req: Request = if (t.isBlank()) chain.request()
        else chain.request().newBuilder().header("Authorization", "Bearer $t").build()
        return chain.proceed(req)
    }
}
