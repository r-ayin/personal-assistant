package com.personalassistant.feature.verify

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.personalassistant.ui.components.VerifyBadge

@Composable
fun VerifyScreen(vm: VerifyViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(
        Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Button(onClick = vm::run, enabled = !ui.running) {
            if (ui.running) CircularProgressIndicator(strokeWidth = 2.dp) else Text("运行反幻觉体检")
        }
        ui.assertion?.let {
            VerifyBadge(passed = ui.passed, detail = it)
        }
        ui.rep?.let {
            Text("体检报告：", style = MaterialTheme.typography.titleLarge)
            Text(it.toString(), style = MaterialTheme.typography.bodyMedium)
        }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (ui.assertion == null && ui.error == null && !ui.running) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("点击运行体检", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
