package com.personalassistant.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val PaDarkColors = darkColorScheme(
    background = PaBackground,
    surface = PaSurface,
    surfaceVariant = PaSurfaceVariant,
    primary = PaPrimary,
    onPrimary = PaOnPrimary,
    secondary = PaSecondary,
    onSecondary = PaOnSecondary,
    tertiary = PaTertiary,
    onTertiary = PaOnTertiary,
    error = PaError,
    onError = PaOnError,
    onBackground = PaOnBackground,
    onSurface = PaOnSurface,
    outline = PaOutline,
)

private val PaLightColors = lightColorScheme(
    primary = PaPrimary,
    secondary = PaSecondary,
    tertiary = PaTertiary,
    error = PaError,
)

/**
 * App 默认暗主题。语义色（绿=溯源/金=反幻觉/红=警示）强相关，故默认**关闭**动态取色
 * 以保语义稳定；用户开"跟随系统壁纸"时才用 dynamicColorScheme 并回退到 PaDarkColors。
 */
@Composable
fun PersonalAssistantTheme(
    darkTheme: Boolean = true,                       // 默认暗
    dynamicColor: Boolean = false,                   // 默认关动态取色
    content: @Composable () -> Unit,
) {
    val ctx = LocalContext.current
    val scheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        darkTheme -> PaDarkColors
        else -> PaLightColors
    }
    MaterialTheme(colorScheme = scheme, typography = PaTypography, content = content)
}
