# Personal Assistant — Android App

Kotlin + Jetpack Compose + Material 3，随身端：对话 / 被动录音上传 / 提醒通知。仅经 REST 消费后端大脑（`personal-assistant/personal_assistant/api.py`，21 端点）。设计稿见 `planning/android-app-design.md`。

## ⚠️ 本开发盒不能编译
此盒无 Android SDK / Gradle / javac（仅 JRE 21），网络受限下不动 Android 工具链。**源码已写齐，验证构建请在有 Android Studio 的机器进行**：
1. 把 `personal-assistant/android/` 拷到开发机（或 GPU 盒）。
2. 生成 Gradle Wrapper（本仓库**未提交 `gradle-wrapper.jar` 二进制**）：在该机装 Gradle 后跑 `gradle wrapper --gradle-version 8.2`，或直接用 Android Studio "Open" 此目录自动 sync。
3. Android Studio 装对应 SDK（compileSdk 34 / minSdk 29），Sync → Run。

## 架构（单模块 :app，包内分层）
```
com.personalassistant
 ├─ ui/theme      Color/Type/Theme（Web 语义色→M3 ColorScheme，暗主题为主）
 ├─ ui/components TimeChip/SourceChip/VerifyBadge/Timeline（反幻觉可见性载体）
 ├─ ui/nav        PaApp（NavHost + 底部 NavigationBar，11 屏路由）
 ├─ data          AppConfig(DataStore) / PaClient(动态 BASE_URL) / PaRepository / DiModule(Hilt) / api.PaApi / model.Dtos
 ├─ feature/*     各屏 ViewModel + Screen（chat 已实现，余 Phase 2）
 └─ service       NotificationChannels / ListeningService(Phase 2)
```

## 三条硬约束（贯穿）
1. **本地优先/隐私**：App 仅持 BASE_URL(+可选 token)，LLM key 由后端 `/settings/llm` 代理、不落 App、不回显。
2. **反幻觉可见**：每条数据带溯源 chip（`SourceChip`）；时间戳标 `time_kind`（`TimeChip`）；LLM 生成 vs 确定性解析视觉区分（绿=确定性/金=LLM原文）。
3. **诚实配置**：思考档位不前端捏造 budget，展示后端 `native_preview` + `uses_max_completion_tokens`。

## 端点→屏映射
见 `planning/android-app-design.md` §6 总表。`PaApi` 21 端点全声明；DTO 字段对齐 `api.py` 真实 shape。

## 阶段
- ✅ Phase 1：工程脚手架 + 主题 + 组件 + 数据层 + 导航 + Chat 屏（参考实现）
- ⏳ Phase 2：memory/persona/calendar/reminder/verify/recommend/wiki/inbox/settings/dashboard 10 屏 + ListeningService + WorkManager
- ⏳ Phase 3：通知跳深链 + 权限请求时序 + 整合自检
