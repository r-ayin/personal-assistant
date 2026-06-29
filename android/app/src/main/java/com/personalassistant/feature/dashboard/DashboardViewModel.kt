package com.personalassistant.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.HealthOut
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DashboardUiState(
    val health: HealthOut? = null,
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(DashboardUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.health()
            .onSuccess { h -> _ui.update { it.copy(health = h, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }
}
