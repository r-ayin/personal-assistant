package com.personalassistant.service

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.personalassistant.MainActivity
import com.personalassistant.R
import com.personalassistant.data.PaClient
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.Reminder
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.util.concurrent.TimeUnit

/**
 * 定期轮询 /reminders/check，到期提醒发 Android 本地通知。
 * 每 60 秒执行一次（最小周期；WorkManager >=15m 限制通过 MinPeriodFlex 绕过）。
 */
@HiltWorker
class ReminderWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    companion object {
        const val WORK_NAME = "pa_reminder_check"
        const val NOTIFICATION_ID_BASE = 7000

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<ReminderWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                req,
            )
        }
    }

    override suspend fun doWork(): Result {
        val client = PaClient(
            okhttp3.OkHttpClient(),
            kotlinx.serialization.json.Json { ignoreUnknownKeys = true },
        )
        val repo = PaRepository(client)
        return repo.remindersCheck().fold(
            onSuccess = { out ->
                for (item in out.items) {
                    if (item.fired != 1) continue
                    showNotification(item)
                }
                Result.success()
            },
            onFailure = { Result.retry() },
        )
    }

    private fun showNotification(reminder: Reminder) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(applicationContext, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) return
        }

        val intent = Intent(applicationContext, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("nav_to", "chat")
        }
        val pending = PendingIntent.getActivity(
            applicationContext, reminder.id.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notif = NotificationCompat.Builder(applicationContext, NotificationChannels.REMINDER)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("⏰ ${reminder.what ?: "到时提醒"}")
            .setContentText(reminder.when_raw ?: "")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()

        try {
            NotificationManagerCompat.from(applicationContext)
                .notify(NOTIFICATION_ID_BASE + (reminder.id?.hashCode()?.and(0x7FFFFFFF) ?: 0), notif)
        } catch (_: SecurityException) {}
    }
}
