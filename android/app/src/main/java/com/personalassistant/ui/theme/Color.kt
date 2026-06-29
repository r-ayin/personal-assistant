package com.personalassistant.ui.theme

import androidx.compose.ui.graphics.Color

// Web 端语义 token → Android 颜色（对齐 frontend-design.md §4 / android-app-design.md §2.1）
// 暗底 / 主色靛蓝 / 溯源绿 / 反幻觉金 / 警示红
val PaBackground = Color(0xFF0E1116)
val PaSurface = Color(0xFF0E1116)
val PaSurfaceVariant = Color(0xFF1A1F27)

val PaPrimary = Color(0xFF5B8DEF)       // 靛蓝
val PaOnPrimary = Color(0xFFFFFFFF)

val PaSecondary = Color(0xFF3FB68B)     // 溯源绿（SourceChip）
val PaOnSecondary = Color(0xFF0E1116)

val PaTertiary = Color(0xFFE0A458)      // 反幻觉金（TimeChip 角标 / 确定性解析）
val PaOnTertiary = Color(0xFF0E1116)

val PaError = Color(0xFFE0584F)         // 警示红（verify 失败）
val PaOnError = Color(0xFFFFFFFF)

val PaOnBackground = Color(0xFFE6E8EC)
val PaOnSurface = Color(0xFFE6E8EC)
val PaOutline = Color(0xFF2A313C)
