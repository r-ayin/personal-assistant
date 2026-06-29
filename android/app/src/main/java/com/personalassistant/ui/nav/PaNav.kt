package com.personalassistant.ui.nav

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.personalassistant.feature.calendar.CalendarScreen
import com.personalassistant.feature.chat.ChatScreen
import com.personalassistant.feature.dashboard.DashboardScreen
import com.personalassistant.feature.memory.MemoryScreen
import com.personalassistant.feature.persona.PersonaScreen
import com.personalassistant.feature.recommend.RecommendScreen
import com.personalassistant.feature.reminder.ReminderScreen
import com.personalassistant.feature.settings.SettingsScreen
import com.personalassistant.feature.verify.VerifyScreen
import com.personalassistant.feature.wiki.WikiScreen

object Routes {
    const val CHAT = "chat"
    const val MEMORY = "memory"
    const val CALENDAR = "calendar"
    const val DASHBOARD = "dashboard"   // "我的"
    const val PERSONA = "persona"
    const val REMINDER = "reminder"
    const val VERIFY = "verify"
    const val RECOMMEND = "recommend"
    const val WIKI = "wiki"
    const val SETTINGS = "settings"
}

private data class Tab(val route: String, val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab(Routes.CHAT, "对话", Icons.Filled.Chat),
    Tab(Routes.MEMORY, "记忆", Icons.Filled.Memory),
    Tab(Routes.CALENDAR, "日历", Icons.Filled.CalendarMonth),
    Tab(Routes.DASHBOARD, "我的", Icons.Filled.Person),
)

private data class Overflow(val route: String, val label: String)

private val OVERFLOW = listOf(
    Overflow(Routes.PERSONA, "数字分身"),
    Overflow(Routes.REMINDER, "提醒"),
    Overflow(Routes.VERIFY, "反幻觉体检"),
    Overflow(Routes.RECOMMEND, "推荐"),
    Overflow(Routes.WIKI, "个人 wiki"),
    Overflow(Routes.SETTINGS, "设置"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaApp() {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val current = backStack?.destination?.route
    var menuOpen by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(TABS.firstOrNull { it.route == current }?.label ?: "个人助手") },
                actions = {
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        OVERFLOW.forEach { o ->
                            DropdownMenuItem(
                                text = { Text(o.label) },
                                onClick = { menuOpen = false; nav.navigate(o.route) },
                            )
                        }
                    }
                },
            )
        },
        bottomBar = {
            // 动森风：悬浮圆角 dock
            Surface(
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 3.dp,
                shape = RoundedCornerShape(28.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
            ) {
                NavigationBar(
                    containerColor = Color.Transparent,
                    tonalElevation = 0.dp,
                ) {
                    TABS.forEach { tab ->
                        NavigationBarItem(
                            selected = current == tab.route,
                            onClick = {
                                nav.navigate(tab.route) {
                                    launchSingleTop = true
                                    restoreState = true
                                    popUpTo(Routes.CHAT) { saveState = true }
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { inner ->
        NavHost(
            navController = nav,
            startDestination = Routes.CHAT,
            modifier = Modifier.padding(inner),
        ) {
            composable(Routes.CHAT) { ChatScreen() }
            composable(Routes.MEMORY) { MemoryScreen() }
            composable(Routes.CALENDAR) { CalendarScreen() }
            composable(Routes.DASHBOARD) { DashboardScreen() }
            composable(Routes.PERSONA) { PersonaScreen() }
            composable(Routes.REMINDER) { ReminderScreen() }
            composable(Routes.VERIFY) { VerifyScreen() }
            composable(Routes.RECOMMEND) { RecommendScreen() }
            composable(Routes.WIKI) { WikiScreen() }
            composable(Routes.SETTINGS) { SettingsScreen() }
        }
    }
}
