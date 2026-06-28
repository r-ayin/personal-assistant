# personal-assistant — 进度

> 直导式构建。v0.1 深核主干；v0.2 说话人/日历/提醒/反幻觉；v0.3 推荐联网搜索；v0.4 个人 wiki；v0.5 LLM 可配 + 前端设计文档。

## 当前状态（2026-06-29）
- ✅ v0.1 深核 MVP 端到端跑通（ASR→记忆→蒸馏→对话→主动）
- ✅ v0.2 扩展端到端跑通：
  - **设备已自带转录** → ASR 降为可选回退；接入改为接收转录文本(.txt/.srt)+可选音频
  - **说话人区分**（音频+文字融合）：TextDiarizer(dev,文字+标签启发式) / PyannoteDiarizer(prod,lazy,GPU盒)；实测 A→user、B→他人
  - **自动日历**：LLM 抽事件+when_raw → temporal 确定性解析绝对日期 → SQLite events → 检索"明天/上周/本月"秒出
  - **定时提醒**：LLM 抽意图+when_raw → 确定性解析 → 到点触发通知（循环类重排）
  - **反幻觉 verify**：每轮 ingest 后脚本复查——when_dt 用 temporal 确定性重解覆盖、when_raw/记忆内容溯源到源转录、不落地即删；assert_no_hallucination 断言
  - **真实时间戳**：now_iso=系统本地实时；段/对话/日历全用；chat_log 存对话真实时间戳
- ✅ v0.3 推荐引擎（联网动态搜索）：
  - Bing Web Search API + 可切 `ApiWebSearcher` 后端；写死推荐池已删
  - 推荐流程：蒸馏人格/兴趣 → LLM 生成搜索词 → 联网搜索 → LLM 筛选+排序 → 存储
  - 反幻觉：推荐内容溯源到搜索结果 URL+snippet，无源不推
- ✅ v0.4 个人 wiki：
  - 记忆→切片+分类→编译互链主题页+源引用；主题动态增长（增量 build）
  - 反幻觉：wiki 内容溯源到记忆条目，记忆溯源到源转录
- ✅ v0.5 LLM 可插拔配置增强：
  - 5 旋钮可配：model / context_window / max_tokens / thinking_effort(off·低·中·高) / base_url(api) / api_key
  - 全局覆盖层：`config.set_override` 运行态覆盖 + env(PA_LLM_MODEL/BASE_URL/API_KEY/MAX_TOKENS/THINKING/THINKING_FORMAT) + `llm.*` 全局默认回落
  - 思考程度档位→provider 原生字段（按官方文档实测，不捏造）：GLM(openai_compat 仅开/关) / GLM-anthropic(budget) / OpenAI(reasoning_effort+max_completion_tokens) / Qwen(enable_thinking+thinking_budget) / Anthropic(thinking.budget_tokens)
  - 新增 `glm_anthropic` 后端（走 `open.bigmodel.cn/api/anthropic`）使 GLM 也能分低/中/高
  - `cli llm` 查生效配置（key 掩码）+ native 字段预览
  - 新端点：`GET/POST /settings/llm`、`POST /inbox/upload`（原始 body+filename，免 multipart）
- ✅ 测试体系：
  - `tests/test_llm_config.py` 10/10 绿（可插拔旋钮+覆盖层+思考档位）
  - `tests/test_pluggable.py` 41 用例（工厂路由/stub 合约/接口不变量/ABC 继承）
  - pytest wrapper `tests/test_e2e_pytest.py`（stub 全链路端到端）
  - stub 全链路 PASS + 真 GLM-5.2（会话代理）全链路 PASS（含反幻觉断言）
- ✅ 前端设计文档 `planning/frontend-design.md`（14 节 + 附录 A 四家真实参数，供外部实现回接）

## 阶段
- [x] Phase 0 脚手架+ASR 接口+后端骨架
- [x] Phase 1 接入(转录解析)→说话人归属→片段库
- [x] Phase 2 记忆抽取+检索
- [x] Phase 3 蒸馏引擎+人格档案
- [x] Phase 4 被动对话
- [x] Phase 5 主动触发引擎
- [x] v0.2 说话人区分(音频+文字) + 日历 + 提醒 + 反幻觉 verify + 真实时间戳
- [x] v0.3 推荐引擎(联网动态搜索 Bing/可切API + 反幻觉)
- [x] v0.4 个人 wiki(记忆→切片+分类+编译互链主题页+源引用 + 反幻觉)
- [x] v0.5 LLM 可配(5旋钮+思考程度档位+全局覆盖+cli llm+3新端点) + 前端设计文档
- [ ] 后补：安卓 App / Web 面板实现 / pyannote 真声纹(GPU盒) / faster-whisper 真模型

## 命令
```bash
python3 -m personal_assistant.cli test                                       # stub 全链路
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test        # 真 GLM-5.2
python3 -m personal_assistant.cli llm                                        # 查生效 LLM 配置
PA_LLM_BACKEND=openai_compat PA_LLM_THINKING=高 python3 -m personal_assistant.cli llm  # 改思考程度
python3 -m personal_assistant.cli pipeline --once                            # 灌 inbox 转录
python3 -m personal_assistant.cli calendar 明天                              # 日历检索
python3 -m personal_assistant.cli reminders                                  # 提醒列表
python3 -m personal_assistant.cli verify                                     # 反幻觉复查
python3 -m personal_assistant.cli serve                                      # API
```
