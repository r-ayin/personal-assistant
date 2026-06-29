package com.personalassistant.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.sp

// 正文 14/16、标题 20/24（对齐设计稿）。中文优先 PingFang/思源黑体由系统兜底；
// 如需内置字体，放 res/font 后在此引用 FontFamily(Font(R.font.xxx))。
val PaFontFamily = FontFamily.Default

val PaTypography = Typography(
    bodyMedium = TextStyle(fontFamily = PaFontFamily, fontSize = 14.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontFamily = PaFontFamily, fontSize = 16.sp, lineHeight = 24.sp),
    titleLarge = TextStyle(fontFamily = PaFontFamily, fontSize = 20.sp, lineHeight = 28.sp),
    headlineMedium = TextStyle(fontFamily = PaFontFamily, fontSize = 24.sp, lineHeight = 32.sp),
    labelSmall = TextStyle(fontFamily = PaFontFamily, fontSize = 11.sp, lineHeight = 14.sp),
)
