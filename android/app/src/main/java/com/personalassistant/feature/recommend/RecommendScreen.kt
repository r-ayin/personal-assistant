package com.personalassistant.feature.recommend

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import com.personalassistant.data.model.Recommendation
import com.personalassistant.ui.components.SourceChip

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecommendScreen(vm: RecommendViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val kinds = listOf("book" to "书", "film" to "影", "way" to "做事方式")
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            kinds.forEach { (k, label) ->
                FilterChip(
                    selected = ui.kind == k,
                    onClick = { vm.kind(k); vm.load() },
                    label = { Text(label) },
                )
            }
        }
        OutlinedTextField(
            value = ui.q,
            onValueChange = vm::query,
            placeholder = { Text("兴趣关键词") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            trailingIcon = { androidx.compose.material3.TextButton(onClick = vm::load) { Text("搜") } },
        )
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            ui.error != null -> Text(ui.error!!, color = MaterialTheme.colorScheme.error)
            ui.recs.isEmpty() -> Text("无推荐", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(ui.recs) { r -> RecCard(r) }
            }
        }
    }
}

@Composable
private fun RecCard(r: Recommendation) {
    Column(Modifier.fillMaxWidth()) {
        Text(r.item ?: "(无)", style = MaterialTheme.typography.titleLarge)
        r.reason?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
        r.based_on?.let { SourceChip(it, onClick = {}) }
    }
}
