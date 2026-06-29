package com.personalassistant.feature.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import com.personalassistant.data.model.Memory
import com.personalassistant.data.model.Segment
import com.personalassistant.ui.components.TimelineItem
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MemoryUiState(
    val segments: List<Segment> = emptyList(),
    val memories: List<Memory> = emptyList(),
    val tab: Int = 0,
    val loading: Boolean = false,
    val error: String? = null,
) {
    val segItems: List<TimelineItem>
        get() = segments.map {
            TimelineItem(
                id = it.id,
                primary = it.text ?: "(无文本)",
                secondary = it.speaker,
                createdAt = it.created_at,
                timeKind = it.time_kind,
                sources = listOf("segment:${it.id}"),
            )
        }

    val memItems: List<TimelineItem>
        get() = memories.map {
            TimelineItem(
                id = it.id,
                primary = it.content ?: "",
                secondary = it.kind,
                createdAt = it.created_at,
                sources = listOfNotNull(it.evidence?.takeIf { e -> e.contains(':') }),
            )
        }
}

@HiltViewModel
class MemoryViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(MemoryUiState())
    val ui = _ui.asStateFlow()

    init { load() }

    fun tab(t: Int) = _ui.update { it.copy(tab = t) }

    fun load() = viewModelScope.launch {
        _ui.update { it.copy(loading = true, error = null) }
        val seg = repo.segments().getOrNull()
        val mem = repo.memories().getOrNull()
        val err = if (seg == null && mem == null) "加载失败（检查 BASE_URL）" else null
        _ui.update {
            it.copy(
                segments = seg?.segments ?: emptyList(),
                memories = mem?.memories ?: emptyList(),
                loading = false,
                error = err,
            )
        }
    }
}
