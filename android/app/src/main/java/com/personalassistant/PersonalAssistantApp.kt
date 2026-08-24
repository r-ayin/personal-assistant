package com.personalassistant

import android.app.Application
import com.personalassistant.service.NotificationChannels
import com.personalassistant.service.ReminderWorker
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class PersonalAssistantApp : Application() {
    override fun onCreate() {
        super.onCreate()
        NotificationChannels.create(this)
        ReminderWorker.schedule(this)
    }
}
