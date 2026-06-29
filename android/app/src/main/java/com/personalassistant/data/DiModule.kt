package com.personalassistant.data

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DiModule {

    @Provides @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true      // 后端字段演进容错
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
    }

    @Provides @Singleton
    fun provideOkHttp(): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        return OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .addInterceptor(logging)
            .build()
    }

    /**
     * PaClient 持有可变 BASE_URL；鉴权 token 通过 AuthInterceptor 注入（PaClient 内部已包）。
     * BASE_URL/token 在用户设置页调用 [PaClient.rebuild] 时刷新。
     */
    @Provides @Singleton
    fun providePaClient(httpClient: OkHttpClient, json: Json): PaClient = PaClient(httpClient, json)

    @Provides @Singleton
    fun provideRepository(client: PaClient): PaRepository = PaRepository(client)

    @Provides @Singleton
    fun provideAppConfig(@ApplicationContext ctx: android.content.Context): AppConfig = AppConfig(ctx)
}
