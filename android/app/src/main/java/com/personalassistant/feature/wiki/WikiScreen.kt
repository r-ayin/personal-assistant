package com.personalassistant.feature.wiki

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import com.personalassistant.data.model.WikiPage
import com.personalassistant.ui.components.SourceChip

@Composable
fun WikiScreen(vm: WikiViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = ui.tag, onValueChange = vm::tag,
                placeholder = { Text("标签") }, modifier = Modifier.weight(1f), singleLine = true,
            )
            OutlinedTextField(
                value = ui.q, onValueChange = vm::query,
                placeholder = { Text("词") }, modifier = Modifier.weight(1f), singleLine = true,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = vm::load) { Text("检索") }
            Button(onClick = vm::build, enabled = !ui.building) {
                if (ui.building) CircularProgressIndicator(strokeWidth = 2.dp) else Text("增量构建")
            }
        }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            ui.pages.isEmpty() -> Text("无 wiki 页", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(ui.pages) { p -> WikiCard(p) }
            }
        }
    }
}

@Composable
private fun WikiCard(p: WikiPage) {
    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(bottom = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(p.title ?: "(无标题)", style = MaterialTheme.typography.titleLarge)
        if (p.tags.isNotEmpty()) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                p.tags.forEach { t -> AssistChip(onClick = {}, label = { Text(t) }) }
            }
        }
        Text(p.body ?: "", style = MaterialTheme.typography.bodyMedium)
        if (p.source_ids.isNotEmpty()) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("溯源:", style = MaterialTheme.typography.labelSmall)
                p.source_ids.take(4).forEach { SourceChip("memory:$it", onClick = {}) }
            }
        }
        if (p.link_ids.isNotEmpty()) {
            Text("链接: ${p.link_ids.joinToString(", ")}", style = MaterialTheme.typography.labelSmall)
        }
        HorizontalDivider()
    }
}
