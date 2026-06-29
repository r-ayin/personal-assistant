package com.personalassistant.ui.theme

import androidx.compose.ui.graphics.Color

// 动森 Pocket Camp 风：暖奶油底 + 叶绿/天蓝/蜜糖/珊瑚柔和 pastel。
// 语义保留：secondary 绿=确定性解析/溯源，tertiary 蜜糖=LLM 原文/时间，error 珊瑚=警示。
// primary 天蓝=主操作/己方对话气泡（AC 标志蓝）。
val PaBackground = Color(0xFFFBF4E6)        // 暖奶油底
val PaSurface = Color(0xFFFFFCF5)           // 暖白卡片
val PaSurfaceVariant = Color(0xFFF0E6D2)    // 暖米色

val PaPrimary = Color(0xFF5BA7C9)           // 天蓝（主操作 / 己方气泡）
val PaOnPrimary = Color(0xFFFFFFFF)

val PaSecondary = Color(0xFF4F9D5C)         // 叶绿（确定性解析 / SourceChip 溯源）
val PaOnSecondary = Color(0xFFFFFFFF)

val PaTertiary = Color(0xFFF2A342)          // 蜜糖橙（TimeChip / LLM 原文 / 反幻觉标记）
val PaOnTertiary = Color(0xFFFFFFFF)

val PaError = Color(0xFFE5736B)             // 珊瑚红（verify 失败）
val PaOnError = Color(0xFFFFFFFF)

val PaOnBackground = Color(0xFF5D4E3C)      // 暖棕文字（AC 文字不是纯黑）
val PaOnSurface = Color(0xFF5D4E3C)
val PaOutline = Color(0xFFE0D6BE)           // 暖米色描边
