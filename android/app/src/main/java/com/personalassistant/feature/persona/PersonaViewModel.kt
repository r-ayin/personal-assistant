package com.personalassistant.feature.persona

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.ProfileOut
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PersonaUiState(
    val version: Int? = null,
    val changeSummary: String? = null,
    val profile: Map<String, String> = emptyMap(),
    val distilling: Boolean = false,
    val distillResult: String? = null,
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class PersonaViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(PersonaUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.profile()
            .onSuccess { p: ProfileOut ->
                _ui.update {
                    it.copy(
                        version = p.version,
                        changeSummary = p.change_summary,
                        profile = p.profile,
                        loading = false,
                    )
                }
            }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }

    fun distill() = viewModelScope.launch {
        _ui.update { it.copy(distilling = true) }
        repo.distill()
            .onSuccess { obj -> _ui.update { it.copy(distilling = false, distillResult = obj.toString()) } }
            .onFailure { e -> _ui.update { it.copy(distilling = false, error = e.message) } }
    }
}
