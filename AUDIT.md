# 全面审计清单

## API 端点完整清单（后端应有 vs 实际有）

| 端点 | 期望 | 实际 | 前端调用 |
|------|------|------|---------|
| GET /health | 200 | 200 ✅ | api.js bootstrap |
| GET /segments | 200 | 200 ✅ | api.js / InboxPage |
| GET /memories | 200 | 200 ✅ | api.js / MemoriesPage |
| GET /events | 200 | 200 ✅ | api.js / CalendarPage |
| GET /reminders | 200 | 200 ✅ | api.js / RemindersPage |
| GET /speakers | 200 | 200 ✅ | api.js / InboxPage |
| GET /chat-log | 200 | 200 ✅ | api.js / ChatPage |
| GET /profile | 200 | 200 ✅ | api.js / PersonaPage |
| POST /verify | 200 | 200 ✅ | api.js / VerifyPage |
| GET /recommend | 200 | 200 ✅ | api.js / RecommendPage |
| GET /wiki | 200 | 200 ✅ | api.js / WikiPage |
| GET /status | 200 | 200 ✅ | DashboardPage(未调用) |
| GET /settings/llm | 200 | 200 ✅ | SettingsPage |
| GET /agents | 200 | 200 ✅ | api.js / AgentsPage |
| GET /interventions | 200 | 200 ✅ | api.js / DashboardPage |
| POST /chat | 200 | 200 ✅ | ChatPage |
| POST /ingest | 200 | 200 ✅ | InboxPage |
| POST /chat/clear | 200 | 200 ✅ | ChatPage |
| POST /settings/llm | 200 | 200 ✅ | SettingsPage |
| POST /interventions/scan | 200 | 200 ✅ | DashboardPage |
| POST /memories/search | 200 | 200 ✅ | MemoriesPage |
| POST /distill | 200 | 200 ✅ | PersonaPage |
| POST /inbox/upload | 200 | 200 ✅ | InboxPage |
| POST /agents | 200 | 200 ✅ | —(未调用) |
| PUT /agents/{id} | 200 | 200 ✅ | AgentsPage |
| **POST /wiki/build** | 200 | ❌ 404 | WikiPage |
| POST /proactive | 200 | 200 ✅ | —(未调用) |
| GET /segments/search | 200 | 200 ✅ | —(未调用) |

## 每个页面的硬编码数据

| 页面 | 硬编码数据 | 应来源 |
|------|-----------|--------|
| MockData.jsx | segments(7条)/memories(7条)/events(3)/reminders(4)/chatLog(4)/speakers(2)/persona/wikiPages(4)/verifyReport/interventions(3)/recommendations/health | ✅ bootstrap可覆盖但空数组不覆盖 |
| DashboardPage | 名称硬编码"今日 · 你的助手在替你看着这些" | ✅ UI文案可接受 |
| CalendarPage | ⚠️ mock事件日期固定 | 后端events |
| PersonaPage | 维度名称映射硬编码dimNameMap | 后端profile |
| VerifyPage | ⚠️ mock无items时全空 | 后端verify已加items |
| chat | ⚠️ 降级文案"（无回复：后端不可达，回落 mock）" | 可接受 |

## 前端按钮/交互完整清单

| 页面 | 交互元素 | 状态 |
|------|---------|------|
| Dashboard - 体检详情 | 跳转 verify | ✅ |
| Dashboard - 进入对话 | 跳转 chat | ✅ |
| Dashboard - 立即扫描触发器 | POST /interventions/scan | ✅ |
| Dashboard - 调整 LLM 配置 | 跳转 settings | ✅ |
| Dashboard - 干预列表 采纳按钮 | 前端only | ❌ 无后端 |
| Inbox - 上传 .txt/.srt | POST /inbox/upload | ✅ |
| Inbox - 立即扫描 inbox | POST /ingest | ✅ |
| Inbox - 点击段落展开详情 | 前端state | ✅ |
| Memories - 搜索 | POST /memories/search | ✅ |
| Memories - 类型筛选 | 前端filter | ✅ |
| Persona - 版本切换 | GET /profile | ✅ |
| Persona - 重新蒸馏 | POST /distill | ✅ |
| Calendar - 自然语言检索 | GET /calendar?q= | ✅ |
| Calendar - 月份翻页 | 前端state | ✅ |
| Calendar - 今天按钮 | 前端state | ✅ |
| Reminders - 立即检查到点 | POST /reminders/check | ✅ |
| Chat - 发送消息 | POST /chat | ✅ |
| Chat - 清空 | POST /chat/clear | ✅ |
| Recommend - 分类切换 | GET /recommend?kind= | ✅ |
| Recommend - 搜索缩窄 | GET /recommend?kind=&q= | ✅ |
| Wiki - 增量构建 | POST /wiki/build | ❌ 404 |
| Wiki - 标签云筛选 | 前端filter | ✅ |
| Wiki - 页面互链跳转 | 前端state | ✅ |
| Verify - 运行run_all | POST /verify | ✅ |
| Verify - 状态筛选 | 前端filter | ✅ |
| Verify - 跳源核查 | 前端dispatch | ❌ 未实现 |
| Settings - 后端切换 | POST /settings/llm | ✅ |
| Settings - 保存配置 | POST /settings/llm | ✅ |
| Settings - 重置 | 前端state | ✅ |
| Agents - 配置按钮 | Modal弹出 | ✅ |
| Agents - 名称/个性保存 | PUT /agents/{id} | ✅ |
