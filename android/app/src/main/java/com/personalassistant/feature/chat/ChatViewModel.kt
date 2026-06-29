package com.personalassistant.feature.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.ChatLogEntry
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatUiState(
    val logs: List<ChatLogEntry> = emptyList(),
    val sending: Boolean = false,
    val draft: String = "",
    val error: String? = null,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {

    private val _ui = MutableStateFlow(ChatUiState())
    val ui: StateFlow<ChatUiState> = _ui.asStateFlow()

    init { loadLog() }

    fun loadLog() = viewModelScope.launch {
        repo.chatLog()
            .onSuccess { data -> _ui.update { it.copy(logs = data.logs.reversed(), error = null) } }
            .onFailure { e -> _ui.update { it.copy(error = e.message ?: "加载失败") } }
    }

    fun draft(s: String) = _ui.update { it.copy(draft = s) }

    fun send() {
        val msg = _ui.value.draft.trim()
        if (msg.isBlank() || _ui.value.sending) return
        val userEntry = ChatLogEntry(role = "user", content = msg, created_at = nowIsoLocal())
        _ui.update { it.copy(draft = "", sending = true, logs = it.logs + userEntry) }
        viewModelScope.launch {
            repo.chat(msg)
                .onSuccess { out ->
                    val reply = ChatLogEntry(role = "assistant", content = out.reply, created_at = nowIsoLocal())
                    _ui.update { it.copy(sending = false, logs = it.logs + reply, error = null) }
                }
                .onFailure { e ->
                    _ui.update { it.copy(sending = false, error = e.message ?: "发送失败") }
                }
        }
    }

    private fun nowIsoLocal(): String =
        java.time.LocalDateTime.now().toString().take(19)
}
