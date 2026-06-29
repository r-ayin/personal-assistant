package com.personalassistant.feature.persona

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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

@Composable
fun PersonaScreen(vm: PersonaViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        ui.version?.let { Text("人格版本 v$it", style = MaterialTheme.typography.titleLarge) }
        ui.changeSummary?.let {
            Text("变更摘要：$it", color = MaterialTheme.colorScheme.tertiary)
        }
        Button(onClick = vm::distill, enabled = !ui.distilling) {
            if (ui.distilling) CircularProgressIndicator(strokeWidth = 2.dp) else Text("重新蒸馏")
        }
        ui.distillResult?.let {
            Text("蒸馏结果：$it", style = MaterialTheme.typography.bodyMedium)
        }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                // 纯文本 9 维，不捏造 score
                items(ui.profile.entries.toList()) { (dim, text) ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(Modifier.padding(12.dp)) {
                            Text(dim, style = MaterialTheme.typography.titleLarge)
                            Text(text, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
