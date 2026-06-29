package com.personalassistant.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: SettingsViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    Column(
        Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("LLM 配置", style = MaterialTheme.typography.titleLarge)

        ChipRow("backend", listOf("stub", "anthropic_proxy", "ollama", "openai_compat", "glm_anthropic"), ui.backend, vm::backend)
        OutlinedTextField(value = ui.model, onValueChange = vm::model, label = { Text("model") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = ui.baseUrl, onValueChange = vm::baseUrl, label = { Text("base_url (api)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(
            value = ui.apiKey, onValueChange = vm::apiKey, label = { Text("api_key（发往后端，不本地保存）") },
            modifier = Modifier.fillMaxWidth(), singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
        )
        OutlinedTextField(value = ui.maxTokens, onValueChange = vm::maxTokens, label = { Text("max_tokens") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = ui.contextWindow, onValueChange = vm::contextWindow, label = { Text("context_window（仅入参，GET 不回显）") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        ChipRow("thinking_effort", listOf("off", "低", "中", "高"), ui.thinkingEffort, vm::thinkingEffort)
        ChipRow("thinking_format", listOf("glm", "openai", "qwen", "anthropic"), ui.thinkingFormat, vm::thinkingFormat)

        Button(onClick = vm::save, enabled = !ui.saving) {
            if (ui.saving) CircularProgressIndicator(strokeWidth = 2.dp) else Text("保存（写运行态覆盖）")
        }
        if (ui.applied.isNotEmpty()) {
            Text("已应用字段：${ui.applied.joinToString(", ")}", color = MaterialTheme.colorScheme.secondary)
        }
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        // 只读：诚实配置——展示后端算好的，不前端捏造
        ui.current?.let { c ->
            Text("生效配置（只读）", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 8.dp))
            Text("api_key(掩码)：${c.api_key_masked ?: "(无)"}", style = MaterialTheme.typography.bodyMedium)
            Text("backend：${c.backend}", style = MaterialTheme.typography.bodyMedium)
            c.native_preview?.let { np ->
                Text("native_preview（按官方文档映射，不捏造 budget）：$np", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.tertiary)
            }
            c.uses_max_completion_tokens?.let { uct ->
                if (uct) Text("uses_max_completion_tokens：true（OpenAI o 系改发 max_completion_tokens）", style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChipRow(label: String, options: List<String>, selected: String, onSelect: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            options.forEach { o ->
                FilterChip(selected = selected == o, onClick = { onSelect(o) }, label = { Text(o) })
            }
        }
    }
}
