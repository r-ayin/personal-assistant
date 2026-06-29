package com.personalassistant.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

/**
 * 四通道（设计稿§4.4）：listening（前台常驻）/ reminder（到点）/ intervention（主动建议）/ chat（分身回复）。
 */
object NotificationChannels {
    const val LISTENING = "pa_listening"
    const val REMINDER = "pa_reminder"
    const val INTERVENTION = "pa_intervention"
    const val CHAT = "pa_chat"

    fun create(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        listOf(
            NotificationChannel(LISTENING, "正在听", NotificationManager.IMPORTANCE_LOW),
            NotificationChannel(REMINDER, "提醒", NotificationManager.IMPORTANCE_HIGH),
            NotificationChannel(INTERVENTION, "主动建议", NotificationManager.IMPORTANCE_DEFAULT),
            NotificationChannel(CHAT, "分身回复", NotificationManager.IMPORTANCE_DEFAULT),
        ).forEach { nm.createNotificationChannel(it) }
    }
}
