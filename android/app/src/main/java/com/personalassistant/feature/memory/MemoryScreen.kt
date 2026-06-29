package com.personalassistant.feature.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.personalassistant.ui.components.Timeline

@Composable
fun MemoryScreen(vm: MemoryViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val tabs = listOf("段落", "记忆")
    Column(Modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = ui.tab) {
            tabs.forEachIndexed { i, t ->
                Tab(selected = ui.tab == i, onClick = { vm.tab(i) }, text = { Text(t) })
            }
        }
        when {
            ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            ui.error != null -> Box(Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.Center) {
                Text(ui.error!!, color = MaterialTheme.colorScheme.error)
            }
            else -> {
                val items = if (ui.tab == 0) ui.segItems else ui.memItems
                LazyColumn(
                    Modifier.fillMaxSize().padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(items) { item -> Timeline(listOf(item)) }
                }
            }
        }
    }
}
