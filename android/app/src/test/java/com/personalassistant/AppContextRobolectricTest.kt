package com.personalassistant

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric 测试：在 JVM 上起 Android 环境，验证应用上下文。
 * 用空 Application 绕过 Hilt 初始化（PersonalAssistantApp 是 @HiltAndroidApp，
 * 实例化会触发 Hilt 组件生成，单测包名不需要它），仅验证 manifest 包名。
 */
@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [34])
class AppContextRobolectricTest {

    @Test
    fun `应用包名为 com personalassistant`() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        assertEquals("com.personalassistant", ctx.packageName)
    }

    @Test
    fun `Application 非空`() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        assertEquals("com.personalassistant", app.packageName)
    }
}
