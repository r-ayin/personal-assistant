package com.personalassistant.feature.reminder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.personalassistant.data.model.Reminder
import com.personalassistant.ui.components.VerifyBadge

@Composable
fun ReminderScreen(vm: ReminderViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Button(onClick = vm::check, enabled = !ui.checking) {
            if (ui.checking) CircularProgressIndicator(strokeWidth = 2.dp) else Text("立即检查到点提醒")
        }
        if (ui.fired.isNotEmpty()) {
            Text("已触发：${ui.fired.joinToString(", ")}", color = MaterialTheme.colorScheme.secondary)
        }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            ui.reminders.isEmpty() -> Text("无提醒", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(ui.reminders) { r -> ReminderRow(r) }
            }
        }
    }
}

@Composable
private fun ReminderRow(r: Reminder) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(r.what ?: "(无内容)", style = MaterialTheme.typography.bodyLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                r.when_raw?.let { Text("raw: $it", color = MaterialTheme.colorScheme.tertiary, style = MaterialTheme.typography.labelSmall) }
                r.when_dt?.let { Text("dt: $it", color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.labelSmall) }
                r.recurring?.let { if (it.isNotBlank()) Text("循环: $it", style = MaterialTheme.typography.labelSmall) }
            }
        }
        if (r.fired == 1) VerifyBadge(passed = true, detail = "已触发")
    }
}
