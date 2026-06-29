package com.personalassistant.service

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.personalassistant.data.PaRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * 上传重试 Worker（设计稿§4.2）：断网缓存转写文本，恢复后重试投递 inbox。
 * 入参 filename/text 经 Data 传入。失败 → Result.retry()。
 */
@HiltWorker
class UploadTranscriptWorker @AssistedInject constructor(
    @Assisted ctx: Context,
    @Assisted params: WorkerParameters,
    private val repo: PaRepository,
) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        val filename = inputData.getString(KEY_FILENAME) ?: return Result.failure()
        val text = inputData.getString(KEY_TEXT) ?: return Result.failure()
        return if (repo.uploadTranscript(filename, text).isSuccess) Result.success() else Result.retry()
    }

    companion object {
        const val KEY_FILENAME = "filename"
        const val KEY_TEXT = "text"
    }
}
