package com.personalassistant.feature.calendar

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.personalassistant.data.model.Event
import com.personalassistant.ui.components.SourceChip

@Composable
fun CalendarScreen(vm: CalendarViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = ui.query,
                onValueChange = vm::query,
                placeholder = { Text("明天 / 上周 / 本月") },
                modifier = Modifier.weight(1f),
                singleLine = true,
            )
            Button(onClick = vm::search) { Text("查") }
        }
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            ui.error != null -> Text(ui.error!!, color = MaterialTheme.colorScheme.error)
            ui.events.isEmpty() -> Text("无事件", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(ui.events) { ev -> EventCard(ev) }
            }
        }
    }
}

@Composable
private fun EventCard(ev: Event) {
    Column(Modifier.fillMaxWidth()) {
        Text(ev.title ?: "(无标题)", style = MaterialTheme.typography.titleLarge)
        listOfNotNull(ev.who, ev.where?.let { "地点：$it" }.takeIf { ev.where != null })
            .forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            // when_raw = LLM 抽取原文（金/tertiary）；when_dt = 确定性解析（绿/secondary）——视觉区分
            ev.when_raw?.let { LabeledChip("LLM原文: $it", MaterialTheme.colorScheme.tertiary, MaterialTheme.colorScheme.onTertiary) }
            ev.when_dt?.let { LabeledChip("解析: $it", MaterialTheme.colorScheme.secondary, MaterialTheme.colorScheme.onSecondary) }
            ev.source_segment?.let { SourceChip(it, onClick = {}) }
        }
    }
}

@Composable
private fun LabeledChip(text: String, bg: androidx.compose.ui.graphics.Color, fg: androidx.compose.ui.graphics.Color) {
    Box(
        Modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 8.dp, vertical = 3.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = fg)
    }
}
