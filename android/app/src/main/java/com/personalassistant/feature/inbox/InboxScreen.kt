package com.personalassistant.feature.inbox

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun InboxScreen(vm: InboxViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(
            value = ui.transcript, onValueChange = vm::transcript,
            placeholder = { Text("贴入转录文本（设备自带转录，.txt 内容）") },
            modifier = Modifier.fillMaxWidth().heightIn(min = 120.dp),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = ui.filename, onValueChange = vm::filename,
                label = { Text("文件名") }, singleLine = true, modifier = Modifier.weight(1f),
            )
            Button(onClick = vm::upload, enabled = !ui.loading) { Text("上传") }
            Button(onClick = vm::ingest, enabled = !ui.loading) { Text("ingest") }
        }
        ui.uploadOut?.let { o ->
            Text("已存 ${o.saved ?: "?"} (${o.bytes ?: 0} bytes) — ${o.ingest_hint ?: ""}", color = MaterialTheme.colorScheme.secondary)
        }
        ui.ingestMsg?.let { Text("ingest: $it", style = MaterialTheme.typography.bodyMedium) }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (ui.loading) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        if (ui.speakers.isNotEmpty()) {
            Text("说话人", style = MaterialTheme.typography.titleLarge)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(ui.speakers) { s ->
                    Text("${s.name} → ${s.label} ${s.note?.let { "($it)" } ?: ""}", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}
