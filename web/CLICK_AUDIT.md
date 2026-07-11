# 完整点击交互审计

## 侧边栏 Sidebar.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 仪表盘 | 主视图 | setRoute("dashboard") | ✅ |
| 对话 | 主视图 | setRoute("chat") | ✅ |
| 接入转录流 | 输入流 | setRoute("inbox") | ✅ |
| 记忆库 | 输入流 | setRoute("memories") | ✅ |
| 自动日历 | 自动化 | setRoute("calendar") | ✅ |
| 定时提醒 | 自动化 | setRoute("reminders") | ✅ |
| 推荐引擎 | 自动化 | setRoute("recommend") | ✅ |
| 数字分身 | 知识/治理 | setRoute("persona") | ✅ |
| 个人 wiki | 知识/治理 | setRoute("wiki") | ✅ |
| 反幻觉体检 | 知识/治理 | setRoute("verify") | ✅ |
| 设备管理 | 设备 | setRoute("agents") | ✅ |
| 设置 / LLM | 系统 | setRoute("settings") | ✅ |
| 用户头像 | 左下角 | 无事件 | ❌ 空按钮 |

## 仪表盘 DashboardPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 体检详情 | header 右 | navigate("verify") | ✅ |
| 进入对话 | header 右 | navigate("chat") | ✅ |
| 立即扫描触发器 | 干预卡片标题右 | POST /interventions/scan | ✅ |
| 采纳 → | 干预列表每项 | 无后端 | ❌ 前端 only |
| 调整 LLM 配置 | 后端状态卡片 | navigate("settings") | ✅ |
| 全部 → | 最新接入段落 | navigate("inbox") | ✅ |
| 全部 → | 未触发提醒 | navigate("reminders") | ✅ |

## 接入转录流 InboxPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 说话人筛选 | 顶部 | setFilter("all"/"A"/"B") | ✅ |
| 设备筛选 | 顶部 | setAgentFilter 下拉 | ❌ 选中不刷新数据 |
| 上传 .txt/.srt | header 右 | POST /inbox/upload | ✅ |
| 立即扫描 inbox | header 右 | POST /ingest + refresh | ✅ |
| 说话人筛选 | 顶部 | setFilter | ✅ |
| 段落列表每项 | 中间 | setSelected(s.id) | ✅ |
| 派生记忆 SourceChip | 详情面板 | dispatch source-jump | ✅ |
| 派生事件 SourceChip | 详情面板 | dispatch source-jump | ✅ |
| 派生提醒 SourceChip | 详情面板 | dispatch source-jump | ✅ |

## 记忆库 MemoriesPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 语义搜索输入 | 顶部 | POST /memories/search (debounce) | ✅ |
| 类型筛选 | 顶部 | setKind("all"/"event"/...) | ✅ |
| 记忆卡片 | 列表 | onJumpSegment | ❌ 未实现 |

## 数字分身 PersonaPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 版本选择下拉 | header 右 | get /profile?version= | ❌ 后端无 version 参数 |
| 重新蒸馏 | header 右 | POST /distill + refresh | ✅ |

## 自动日历 CalendarPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 自然语言搜索 | 顶部 | GET /calendar?q= (debounce) | ✅ |
| 上月 | 月历表头 | month-1 | ✅ |
| 下月 | 月历表头 | month+1 | ✅ |
| 今天 | 月历表头 | setDate(today) | ✅ |
| 天数点击 | 月历 | 无事件 | ❌ 无日期点击跳转 |

## 定时提醒 RemindersPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 立即检查到点 | header 右 | POST /reminders/check + refresh | ✅ |

## 对话 ChatPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 附加上传 | composer 左 | 无事件 | ❌ 空按钮 |
| 发送 | composer 右 | POST /chat | ✅ |
| 清空 | header 右 | POST /chat/clear | ✅ |
| evidence SourceChip | 每条回复 | dispatch source-jump | ✅ |

## 推荐引擎 RecommendPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 图书/影片/行动 | header下方 | GET /recommend?kind= | ✅ |
| 搜索缩窄 | header下方 | GET /recommend?kind=&q= | ❌ debounce未实现 |
| based_on SourceChip | 每张卡片 | dispatch source-jump | ✅ |

## 个人 wiki WikiPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 标签云按钮 | 左侧 | setTag | ✅ |
| 搜索 | 左侧 | 前端filter | ✅ |
| 页面列表项 | 左侧 | setActiveId | ✅ |
| 增量构建 | header 右 | POST /wiki/build | ✅ (刚修复) |
| 互链跳转 | 详情 | setActiveId(id) | ✅ |

## 反幻觉体检 VerifyPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 运行 run_all | header 右 | POST /verify + map | ✅ |
| 状态筛选 | 列表上方 | setFilter("all"/"passed"/...) | ✅ |
| 跳源核查 | 每条右侧 | 无事件 | ❌ 空按钮 |

## 设置 SettingsPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 后端切换(6个) | 编辑区 | setBackend | ✅ |
| 保存配置 | 编辑区底部 | POST /settings/llm | ✅ |
| 重置 | 编辑区底部 | 无事件 | ❌ 空按钮 |
| model/base_url输入 | 编辑区 | setModel/setBaseUrl | ✅ |

## 设备管理 AgentsPage.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 配置按钮 | 每台设备 | setEditing + modal弹出 | ✅ |
| Modal - 取消 | Modal | setEditing(null) | ✅ |
| Modal - 保存 | Modal | PUT /agents/{id} + refresh | ✅ |

## Tweaks 浮层 TweaksPanel.jsx
| 按钮 | 位置 | 动作 | 状态 |
|------|------|------|------|
| 收起/展开 | 右上角 | setOpen | ✅ |
| 主色切换4种 | 面板 | setAccent | ✅ |
| 密度切换3种 | 面板 | setDensity | ✅ |
| 溯源显示3种 | 面板 | setShow | ✅ |

## 计划修复问题清单
1. **InboxPage.jsx:143**: `Block is not defined` → 应为 `InboxBlock`
2. InboxPage: 设备筛选选中后不刷新数据（无 effect）
3. DashboardPage: 采纳按钮无后端
4. VerifyPage: 跳源核查空按钮
5. CalendarPage: 日期点击无跳转
6. ChatPage: 附加上传空按钮
7. SettingsPage: 重置空按钮
8. MemoriesPage: 记忆卡片跳转未实现
9. RecommendPage: 搜索 debounce 未实现
10. PersonaPage: 版本切换不支持
