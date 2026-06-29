package com.personalassistant.feature.recommend

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.Recommendation
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RecommendUiState(
    val kind: String = "book",
    val q: String = "",
    val recs: List<Recommendation> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class RecommendViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(RecommendUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun kind(k: String) = _ui.update { it.copy(kind = k) }
    fun query(s: String) = _ui.update { it.copy(q = s) }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.recommend(_ui.value.kind, _ui.value.q)
            .onSuccess { d -> _ui.update { it.copy(recs = d.recommendations, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }
}
