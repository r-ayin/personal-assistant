package com.personalassistant.feature.inbox

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.InboxUploadOut
import com.personalassistant.data.model.Speaker
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class InboxUiState(
    val transcript: String = "",
    val filename: String = "day1.txt",
    val uploadOut: InboxUploadOut? = null,
    val ingestMsg: String? = null,
    val speakers: List<Speaker> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class InboxViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(InboxUiState())
    val ui = _ui.asStateFlow()

    init { loadSpeakers() }

    fun transcript(s: String) = _ui.update { it.copy(transcript = s) }
    fun filename(s: String) = _ui.update { it.copy(filename = s) }

    fun loadSpeakers() = viewModelScope.launch {
        repo.speakers().onSuccess { d -> _ui.update { it.copy(speakers = d.speakers) } }
    }

    fun upload() = viewModelScope.launch {
        val text = _ui.value.transcript
        val fn = _ui.value.filename
        if (text.isBlank()) { _ui.update { it.copy(error = "转录文本为空") }; return@launch }
        _ui.update { it.copy(loading = true, error = null) }
        repo.uploadTranscript(fn, text)
            .onSuccess { o -> _ui.update { it.copy(loading = false, uploadOut = o, ingestMsg = null) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }

    fun ingest() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.ingest()
            .onSuccess { obj -> _ui.update { it.copy(loading = false, ingestMsg = obj.toString()) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }
}
