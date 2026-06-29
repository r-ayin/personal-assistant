package com.personalassistant.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.sp

// 动森 Pocket Camp 风：圆润、亲切、略 chunky。
// ⚠️ 系统 Roboto/Noto 不圆润。要真正 AC 圆体效果，把字体放进 res/font/ 后改：
//    - 拉丁：Nunito / Quicksand / Comfortaa（Google Fonts，免费）
//    - 中文圆体：站酷快乐体 / 悠哉字体 / Fusion Pixel 圆体（免费）
//    然后 FontFamily(Font(R.font.nunito), Font(R.font.<rounded_cjk>))
// 当前用系统兜底，靠配色+大圆角+软阴影承载 AC 感。
val PaFontFamily = FontFamily.Default

val PaTypography = Typography(
    bodyMedium = TextStyle(fontFamily = PaFontFamily, fontSize = 14.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontFamily = PaFontFamily, fontSize = 16.sp, lineHeight = 24.sp),
    titleLarge = TextStyle(fontFamily = PaFontFamily, fontSize = 20.sp, lineHeight = 28.sp),
    headlineMedium = TextStyle(fontFamily = PaFontFamily, fontSize = 24.sp, lineHeight = 32.sp),
    labelSmall = TextStyle(fontFamily = PaFontFamily, fontSize = 11.sp, lineHeight = 14.sp),
)
