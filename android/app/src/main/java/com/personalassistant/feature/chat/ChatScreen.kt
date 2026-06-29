package com.personalassistant.feature.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.personalassistant.ui.components.TimeChip

/**
 * 对话屏（设计稿§3.1）：POST /chat + GET /chat-log。
 * 己方气泡 primary / 分身气泡 surfaceVariant；每条带 TimeChip（真实时间戳）。
 */
@Composable
fun ChatScreen(
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val ui by viewModel.ui.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    LaunchedEffect(ui.logs.size) {
        if (ui.logs.isNotEmpty()) listState.animateScrollToItem(ui.logs.lastIndex)
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            state = listState,
            contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(ui.logs, key = { (it.created_at ?: "") + (it.content ?: "") + (it.role ?: "") }) { entry ->
                MessageBubble(entry)
            }
            if (ui.sending) {
                item {
                    Box(Modifier.fillMaxWidth().padding(8.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(strokeWidth = 2.dp)
                    }
                }
            }
        }
        ui.error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.padding(horizontal = 12.dp),
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedTextField(
                value = ui.draft,
                onValueChange = viewModel::draft,
                placeholder = { Text("和分身说点什么…") },
                modifier = Modifier.weight(1f),
                maxLines = 4,
            )
            IconButton(onClick = viewModel::send, enabled = !ui.sending && ui.draft.isNotBlank()) {
                Icon(Icons.Filled.Send, contentDescription = "发送")
            }
        }
    }
}

@Composable
private fun MessageBubble(entry: com.personalassistant.data.model.ChatLogEntry) {
    val isUser = entry.role == "user"
    val align = if (isUser) Alignment.End else Alignment.Start
    val color = if (isUser) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant
    val onColor = if (isUser) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = align,
    ) {
        Surface(color = color, contentColor = onColor, shape = MaterialTheme.shapes.medium) {
            Text(
                text = entry.content ?: "",
                modifier = Modifier.widthIn(max = 280.dp).padding(horizontal = 12.dp, vertical = 8.dp),
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        Spacer(Modifier.height(2.dp))
        entry.created_at?.let { TimeChip(createdAt = it, modifier = Modifier.padding(horizontal = 4.dp)) }
    }
}
