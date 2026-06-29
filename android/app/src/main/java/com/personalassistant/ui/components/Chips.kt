package com.personalassistant.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/**
 * 时间 chip：显示 [created_at] + [timeKind] 角标。
 * 反幻觉约束（设计稿§0.2/§2.4）：记录时间(received) ≠ 发生时间(occurred)，
 * 角标用 tertiary(金) 标注，长按提示差异。
 */
@Composable
fun TimeChip(
    createdAt: String,
    timeKind: String? = null,
    modifier: Modifier = Modifier,
) {
    val accent = MaterialTheme.colorScheme.tertiary
    Surface(
        color = accent.copy(alpha = 0.14f),
        contentColor = accent,
        shape = RoundedCornerShape(50),
        modifier = modifier,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        ) {
            Text(
                text = createdAt.take(19).replace('T', ' '),
                style = MaterialTheme.typography.labelSmall,
            )
            if (!timeKind.isNullOrBlank()) {
                Box(
                    Modifier
                        .clip(RoundedCornerShape(50))
                        .background(accent)
                        .padding(horizontal = 4.dp)
                ) {
                    Text(
                        text = timeKind,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onTertiary,
                    )
                }
            }
        }
    }
}

/** 解析溯源字符串 → (kind, id)。形如 segment:<id> / result:<N> / persona:<dim> / memory:<id>。 */
fun parseSource(source: String): Pair<String, String> {
    val idx = source.indexOf(':')
    return if (idx > 0) source.substring(0, idx) to source.substring(idx + 1) else "src" to source
}

/**
 * 溯源 chip：点击跳源。用 secondary(绿)。
 * 反幻觉约束：每条数据尽量带溯源；memory.evidence / wiki.source_ids / recommend.based_on 都经此组件。
 */
@Composable
fun SourceChip(
    source: String,
    onClick: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val (kind, id) = parseSource(source)
    Surface(
        color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.16f),
        contentColor = MaterialTheme.colorScheme.secondary,
        shape = RoundedCornerShape(50),
        modifier = modifier.clickable { onClick(source) },
    ) {
        Text(
            text = "$kind:$id",
            style = MaterialTheme.typography.labelSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}

/** Verify 徽章：✅ passed(secondary绿) / ❌ failed(error红)。来自 POST /verify 的 assertion。 */
@Composable
fun VerifyBadge(
    passed: Boolean,
    detail: String? = null,
    modifier: Modifier = Modifier,
) {
    val color = if (passed) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        modifier = modifier,
    ) {
        Icon(
            imageVector = if (passed) Icons.Filled.CheckCircle else Icons.Filled.Error,
            contentDescription = if (passed) "passed" else "failed",
            tint = color,
            modifier = Modifier.size(16.dp),
        )
        if (!detail.isNullOrBlank()) {
            Text(text = detail, style = MaterialTheme.typography.labelSmall, color = color)
        }
    }
}

/** 时间线通用项：用于 segments / chat_log / reminders / events。 */
data class TimelineItem(
    val id: String,
    val primary: String,
    val secondary: String? = null,
    val createdAt: String? = null,
    val timeKind: String? = null,
    val sources: List<String> = emptyList(),
)

@Composable
fun Timeline(
    items: List<TimelineItem>,
    onSourceClick: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items.forEach { item ->
            Column(Modifier.fillMaxWidth()) {
                Text(item.primary, style = MaterialTheme.typography.bodyLarge)
                if (!item.secondary.isNullOrBlank()) {
                    Text(
                        item.secondary,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 2.dp),
                ) {
                    if (item.createdAt != null) {
                        TimeChip(createdAt = item.createdAt, timeKind = item.timeKind)
                    }
                    item.sources.take(3).forEach { SourceChip(it, onSourceClick) }
                }
            }
        }
    }
}
