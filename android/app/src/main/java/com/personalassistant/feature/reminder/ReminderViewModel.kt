package com.personalassistant.feature.reminder

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.Reminder
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ReminderUiState(
    val reminders: List<Reminder> = emptyList(),
    val fired: List<String> = emptyList(),
    val checking: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ReminderViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(ReminderUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.reminders()
            .onSuccess { d -> _ui.update { it.copy(reminders = d.reminders, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }

    fun check() = viewModelScope.launch {
        _ui.update { it.copy(checking = true) }
        repo.remindersCheck()
            .onSuccess { d -> _ui.update { it.copy(checking = false, fired = d.fired) } }
            .onFailure { e -> _ui.update { it.copy(checking = false, error = e.message) } }
    }
}
