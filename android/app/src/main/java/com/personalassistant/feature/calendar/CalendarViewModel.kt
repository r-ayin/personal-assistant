package com.personalassistant.feature.calendar

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.Event
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CalendarUiState(
    val query: String = "",
    val events: List<Event> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class CalendarViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(CalendarUiState())
    val ui = _ui.asStateFlow()

    init { loadAll() }

    fun query(s: String) = _ui.update { it.copy(query = s) }

    fun loadAll() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.events()
            .onSuccess { d -> _ui.update { it.copy(events = d.events, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }

    fun search() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        val q = _ui.value.query
        if (q.isBlank()) {
            loadAll(); return@launch
        }
        repo.calendar(q)
            .onSuccess { d -> _ui.update { it.copy(events = d.events, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }
}
