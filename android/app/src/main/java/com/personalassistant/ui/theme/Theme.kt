package com.personalassistant.ui.theme

import android.os.Build
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

// 动森风：明亮、暖奶油、柔和。默认亮主题。
private val PaColors = lightColorScheme(
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

/**
 * 动森 Pocket Camp 风：默认亮、暖奶油底、大圆角。动态取色默认关（保 AC 调色板稳定）。
 */
@Composable
fun PersonalAssistantTheme(
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val ctx = LocalContext.current
    val scheme = if (dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
        dynamicLightColorScheme(ctx) else PaColors
    MaterialTheme(colorScheme = scheme, typography = PaTypography, shapes = PaShapes, content = content)
}
