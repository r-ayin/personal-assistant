package com.personalassistant.feature.verify

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.personalassistant.data.PaRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import javax.inject.Inject

data class VerifyUiState(
    val assertion: String? = null,
    val rep: JsonObject? = null,
    val running: Boolean = false,
    val error: String? = null,
) {
    val passed: Boolean get() = assertion?.startsWith("passed") == true
}

@HiltViewModel
class VerifyViewModel @Inject constructor(
    private val repo: PaRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(VerifyUiState())
    val ui = _ui.asStateFlow()

    fun run() = viewModelScope.launch {
        _ui.update { it.copy(running = true, error = null) }
        repo.verify()
            .onSuccess { (assertion, rep) -> _ui.update { it.copy(running = false, assertion = assertion, rep = rep) } }
            .onFailure { e -> _ui.update { it.copy(running = false, error = e.message) } }
    }
}
