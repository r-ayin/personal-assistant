package com.personalassistant.feature.wiki

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.WikiPage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class WikiUiState(
    val tag: String = "",
    val q: String = "",
    val pages: List<WikiPage> = emptyList(),
    val building: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class WikiViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(WikiUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun tag(s: String) = _ui.update { it.copy(tag = s) }
    fun query(s: String) = _ui.update { it.copy(q = s) }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        repo.wiki(_ui.value.tag, _ui.value.q)
            .onSuccess { d -> _ui.update { it.copy(pages = d.pages, loading = false) } }
            .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message) } }
    }

    fun build() = viewModelScope.launch {
        _ui.update { it.copy(building = true) }
        repo.wikiBuild()
            .onSuccess { _ui.update { it.copy(building = false) }; load() }
            .onFailure { e -> _ui.update { it.copy(building = false, error = e.message) } }
    }
}
