package com.personalassistant

import android.app.Application
import com.personalassistant.service.NotificationChannels
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class PersonalAssistantApp : Application() {
    override fun onCreate() {
        super.onCreate()
        NotificationChannels.create(this)
    }
}
