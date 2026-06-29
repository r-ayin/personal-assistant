package com.personalassistant.service

import android.app.Notification
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.personalassistant.MainActivity
import com.personalassistant.data.PaRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * 24h 被动听前台服务（设计稿§4.1）。
 * foregroundServiceType=microphone（manifest 已声明）。AudioRecord + 简单 VAD（短时 RMS 阈值）切分语音段。
 *
 * ⚠️ 转写占位：本盒/典型环境缺 OnDevice ASR，[transcribe] 为 TODO——真实现需 whisper.cpp /
 * 平台 SpeechRecognizer，或回退后端 asr.py。有文本后才走 [repo].uploadTranscript 投递 inbox。
 */
@AndroidEntryPoint
class ListeningService : android.app.Service() {

    @Inject lateinit var repo: PaRepository

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var captureJob: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground()
        captureJob = scope.launch { captureLoop() }
        return START_STICKY
    }

    private fun startForeground() {
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notif: Notification = NotificationCompat.Builder(this, NotificationChannels.LISTENING)
            .setContentTitle("正在听…")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setContentIntent(pi)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    /** 采音 + VAD：检测到语音段后调 [transcribe]（占位）。 */
    private suspend fun captureLoop() {
        val sampleRate = 16000
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuf <= 0) return
        var recorder: AudioRecord? = null
        try {
            recorder = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 4,
            )
            if (recorder.state != AudioRecord.STATE_INITIALIZED) return
            val buf = ShortArray(minBuf)
            recorder.startRecording()
            var speaking = false
            while (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                val n = recorder.read(buf, 0, buf.size)
                if (n <= 0) continue
                val rms = rms(buf, n)
                if (rms > VAD_THRESHOLD) {
                    if (!speaking) { speaking = true /* 段开始 */ }
                } else {
                    if (speaking) { speaking = false /* 段结束 → 转写并投递 */; onSegment() }
                }
            }
        } finally {
            recorder?.stop(); recorder?.release()
        }
    }

    private fun rms(buf: ShortArray, n: Int): Double {
        var sum = 0.0
        for (i in 0 until n) { val v = buf[i].toInt(); sum += v * v }
        return kotlin.math.sqrt(sum / n)
    }

    /** 语音段结束：转写（占位）→ 投递 inbox。 */
    private suspend fun onSegment() {
        val text: String? = transcribe()
        if (text.isNullOrBlank()) return  // 无 ASR 暂不投递
        val filename = "seg-${System.currentTimeMillis()}.txt"
        runCatching { repo.uploadTranscript(filename, text) }
    }

    private fun transcribe(): String? {
        // TODO: OnDevice ASR（whisper.cpp / android SpeechRecognizer）或回退后端 asr.py。
        // 本盒无该能力，返回 null（不编造文本，对齐反幻觉）。
        return null
    }

    override fun onDestroy() {
        captureJob?.cancel(); scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val NOTIF_ID = 0xA1
        private const val VAD_THRESHOLD = 1500.0
        fun start(ctx: Context) {
            val i = Intent(ctx, ListeningService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }
        fun stop(ctx: Context) { ctx.stopService(Intent(ctx, ListeningService::class.java)) }
    }
}
