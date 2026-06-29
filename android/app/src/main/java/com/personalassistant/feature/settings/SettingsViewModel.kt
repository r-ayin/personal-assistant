package com.personalassistant.feature.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.LlmSettings
import com.personalassistant.data.model.LlmSettingsIn
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val backend: String = "stub",
    val model: String = "",
    val baseUrl: String = "",
    val apiKey: String = "",          // 用户输入；发往后端不本地持久化
    val maxTokens: String = "",
    val contextWindow: String = "",   // 仅 POST 入参
    val thinkingEffort: String = "off",
    val thinkingFormat: String = "glm",
    val current: LlmSettings? = null,  // GET：含 api_key_masked + native_preview
    val saving: Boolean = false,
    val applied: List<String> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(SettingsUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun load() = viewModelScope.launch {
        repo.llmSettings()
            .onSuccess { c ->
                _ui.update {
                    it.copy(
                        current = c,
                        backend = c.backend,
                        model = c.model ?: it.model,
                        baseUrl = c.base_url ?: it.baseUrl,
                        maxTokens = c.max_tokens?.toString() ?: it.maxTokens,
                        thinkingEffort = c.thinking_effort ?: it.thinkingEffort,
                        thinkingFormat = c.thinking_format ?: it.thinkingFormat,
                    )
                }
            }
            .onFailure { e -> _ui.update { it.copy(error = e.message) } }
    }

    fun backend(v: String) = _ui.update { it.copy(backend = v) }
    fun model(v: String) = _ui.update { it.copy(model = v) }
    fun baseUrl(v: String) = _ui.update { it.copy(baseUrl = v) }
    fun apiKey(v: String) = _ui.update { it.copy(apiKey = v) }
    fun maxTokens(v: String) = _ui.update { it.copy(maxTokens = v.filter { c -> c.isDigit() }) }
    fun contextWindow(v: String) = _ui.update { it.copy(contextWindow = v.filter { c -> c.isDigit() }) }
    fun thinkingEffort(v: String) = _ui.update { it.copy(thinkingEffort = v) }
    fun thinkingFormat(v: String) = _ui.update { it.copy(thinkingFormat = v) }

    fun save() = viewModelScope.launch {
        val s = _ui.value
        _ui.update { it.copy(saving = true, error = null) }
        val inp = LlmSettingsIn(
            backend = s.backend,
            model = s.model.ifBlank { null },
            base_url = s.baseUrl.ifBlank { null },
            api_key = s.apiKey.ifBlank { null },
            max_tokens = s.maxTokens.toIntOrNull(),
            context_window = s.contextWindow.toIntOrNull(),
            thinking_effort = s.thinkingEffort,
            thinking_format = s.thinkingFormat,
        )
        repo.updateLlm(inp)
            .onSuccess { o ->
                _ui.update { it.copy(saving = false, applied = o.applied, current = o.effective ?: s.current, apiKey = "") }
            }
            .onFailure { e -> _ui.update { it.copy(saving = false, error = e.message) } }
    }
}
