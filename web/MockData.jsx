// 全量 Mock 数据，对齐 storage 表结构
const MockData = (() => {
  const segments = [
    { id:"seg_3f9a01", source_file:"2026-06-28-meeting.txt", start_sec:12.4, end_sec:24.8, text:"周三下午三点跟 Lily 在虹桥的星巴克碰，她想聊产品节奏。", speaker:"A", language:"zh", created_at:"2026-06-28 09:14:22", processed:1, time_kind:"received" },
    { id:"seg_3f9a02", source_file:"2026-06-28-meeting.txt", start_sec:25.0, end_sec:38.3, text:"好的，那我顺便把上周整理的用户访谈纪要带去给她看。", speaker:"A", language:"zh", created_at:"2026-06-28 09:14:35", processed:1, time_kind:"received" },
    { id:"seg_3f9a03", source_file:"2026-06-28-meeting.txt", start_sec:39.0, end_sec:55.1, text:"对了我最近在看 Kahneman 的《思考，快与慢》，里面 system1/system2 讲得很透。", speaker:"A", language:"zh", created_at:"2026-06-28 09:15:08", processed:1, time_kind:"received" },
    { id:"seg_3f9a04", source_file:"2026-06-28-meeting.txt", start_sec:55.4, end_sec:70.0, text:"哦那本我也想看，听说后半部分关于 prospect theory 比较绕。", speaker:"B", language:"zh", created_at:"2026-06-28 09:15:30", processed:1, time_kind:"received" },
    { id:"seg_3f9a05", source_file:"2026-06-27-night.txt", start_sec:8.2, end_sec:22.6, text:"明天早上记得给小奶猫喂药，剂量减半，连续三天。", speaker:"A", language:"zh", created_at:"2026-06-27 22:48:11", processed:1, time_kind:"received" },
    { id:"seg_3f9a06", source_file:"2026-06-27-night.txt", start_sec:23.0, end_sec:34.0, text:"下周五前要把数据脱敏方案给到法务那边复核。", speaker:"A", language:"zh", created_at:"2026-06-27 22:48:42", processed:1, time_kind:"received" },
    { id:"seg_3f9a07", source_file:"2026-06-26-walk.txt", start_sec:3.0, end_sec:18.7, text:"我其实不喜欢在嘈杂环境里思考，安静环境效率高很多。", speaker:"A", language:"zh", created_at:"2026-06-26 18:02:55", processed:1, time_kind:"received" },
  ];

  const memories = [
    { id:"mem_a1", segment_id:"seg_3f9a01", kind:"event", content:"周三下午 15:00 与 Lily 在虹桥星巴克见面讨论产品节奏。", evidence:"seg_3f9a01", created_at:"2026-06-28 09:14:30", processed:1 },
    { id:"mem_a2", segment_id:"seg_3f9a03", kind:"preference", content:"喜欢阅读认知心理学类书籍，当前在读 Kahneman《思考，快与慢》。", evidence:"seg_3f9a03", created_at:"2026-06-28 09:15:12", processed:1 },
    { id:"mem_a3", segment_id:"seg_3f9a05", kind:"intention", content:"打算明早给小奶猫喂药（剂量减半，连续三天）。", evidence:"seg_3f9a05", created_at:"2026-06-27 22:48:18", processed:1 },
    { id:"mem_a4", segment_id:"seg_3f9a06", kind:"event", content:"下周五前需提交数据脱敏方案给法务复核。", evidence:"seg_3f9a06", created_at:"2026-06-27 22:48:46", processed:1 },
    { id:"mem_a5", segment_id:"seg_3f9a07", kind:"preference", content:"在安静环境中思考效率更高，避免嘈杂场景下做深度工作。", evidence:"seg_3f9a07", created_at:"2026-06-26 18:03:01", processed:1 },
    { id:"mem_a6", segment_id:"seg_3f9a02", kind:"intention", content:"将上周用户访谈纪要带到与 Lily 的会面中。", evidence:"seg_3f9a02", created_at:"2026-06-28 09:14:40", processed:1 },
    { id:"mem_a7", segment_id:"", kind:"emotion", content:"对接下来一周的工作节奏感到一定压力。", evidence:"", created_at:"2026-06-28 08:50:11", processed:1 },
  ];

  const events = [
    { id:"evt_01", title:"与 Lily 讨论产品节奏", when_dt:"2026-07-01 15:00", when_raw:"周三下午三点", who:"Lily", where:"虹桥 星巴克", source_segment:"seg_3f9a01", created_at:"2026-06-28 09:14:32" },
    { id:"evt_02", title:"提交数据脱敏方案给法务", when_dt:"2026-07-03 18:00", when_raw:"下周五前", who:"法务", where:"邮件", source_segment:"seg_3f9a06", created_at:"2026-06-27 22:48:50" },
    { id:"evt_03", title:"小奶猫服药·第 1 天", when_dt:"2026-06-29 09:00", when_raw:"明天早上", who:"自己 / 小奶猫", where:"家", source_segment:"seg_3f9a05", created_at:"2026-06-27 22:48:22" },
  ];

  const reminders = [
    { id:"rmd_01", what:"喂小奶猫吃药（剂量减半）", when_dt:"2026-06-29 09:00", when_raw:"明天早上", recurring:"daily x3", source_segment:"seg_3f9a05", fired:0, created_at:"2026-06-27 22:48:25" },
    { id:"rmd_02", what:"打包用户访谈纪要带给 Lily", when_dt:"2026-07-01 13:30", when_raw:"周三出门前", recurring:"", source_segment:"seg_3f9a02", fired:0, created_at:"2026-06-28 09:14:42" },
    { id:"rmd_03", what:"提交数据脱敏方案", when_dt:"2026-07-03 17:00", when_raw:"下周五前", recurring:"", source_segment:"seg_3f9a06", fired:0, created_at:"2026-06-27 22:48:52" },
    { id:"rmd_04", what:"每周回顾：本周 OKR 进度", when_dt:"2026-06-28 21:00", when_raw:"每周日晚上", recurring:"weekly", source_segment:"", fired:1, created_at:"2026-06-21 21:00:00" },
  ];

  const chatLog = [
    { id:1, role:"user",      content:"我最近读完了《思考，快与慢》，你觉得我下一本读什么合适？", created_at:"2026-06-28 09:42:11" },
    { id:2, role:"assistant", content:"按你最近偏好（认知心理学+喜欢系统性框架），我建议读 Stuart Russell 的《Human Compatible》或 Daniel Dennett《From Bacteria to Bach and Back》。前者偏 AI 决策与价值对齐，后者偏意识与进化视角，都和 Kahneman 框架可对话。", created_at:"2026-06-28 09:42:14", evidence:["mem_a2","mem_a5"] },
    { id:3, role:"user",      content:"那帮我把这条加进个人 wiki 的「阅读」标签下。", created_at:"2026-06-28 09:43:02" },
    { id:4, role:"assistant", content:"已加入 wiki 页《2026 阅读清单》，并互链到「认知 / 决策」页。增量 wiki 构建会在下次 /wiki/build 触发时合并。", created_at:"2026-06-28 09:43:05", evidence:["wiki_reading"] },
  ];

  const speakers = [
    { name:"A", label:"我自己", note:"主语者，绑定本机", created_at:"2026-04-10 08:00:00" },
    { name:"B", label:"未识别", note:"同事 / 朋友 / 家人混合", created_at:"2026-04-10 08:00:00" },
  ];

  const persona = {
    version: 7,
    change_summary: "新增对认知心理学持续兴趣；强化「安静环境优先」工作偏好；下周计划压力指标 +1。",
    profile: {
      identity:        { score: 0.78, summary:"产品/工程双背景，专注于个人数据系统与隐私优先工具构建。", evidence:["mem_a2","mem_a6"] },
      values:          { score: 0.86, summary:"重视真实性与隐私，反对幻觉式表达，偏好确定性 over 表演性。", evidence:["mem_a5"] },
      cognition:       { score: 0.74, summary:"系统二倾向，偏好框架化思考与可解释模型。", evidence:["mem_a2"] },
      preferences:     { score: 0.81, summary:"安静工作环境；阅读认知/系统论；轻度咖啡因。", evidence:["mem_a5","mem_a7"] },
      relationships:   { score: 0.62, summary:"小圈深度连接：Lily（产品搭档）、家人、宠物。", evidence:["mem_a1","mem_a3"] },
      goals:           { score: 0.69, summary:"两周内交付数据脱敏方案；季度内完成数字分身 v1。", evidence:["mem_a4"] },
      emotionalStyle:  { score: 0.55, summary:"轻度压力下倾向自我加速，对节奏失控敏感。", evidence:["mem_a7"] },
      knowledgeAreas:  { score: 0.72, summary:"认知科学 / 系统设计 / Web 隐私 / 产品节奏。", evidence:["mem_a2","mem_a5"] },
    },
    versions: [
      { v:7, at:"2026-06-28 09:20:00", note:"+ Kahneman 偏好；+ 压力上升信号" },
      { v:6, at:"2026-06-21 09:20:00", note:"+ 数据脱敏目标；- 旧 OKR 项" },
      { v:5, at:"2026-06-14 09:20:00", note:"初次纳入宠物相关意图" },
    ],
  };

  const interventions = [
    { id:"int_01", created_at:"2026-06-28 08:50:11", trigger_kind:"stress_signal", evidence:"mem_a7", message:"检测到本周日程密度高于均值 32%，建议把「数据脱敏方案」预留到周三上午一整段。", delivered:1 },
    { id:"int_02", created_at:"2026-06-28 09:00:00", trigger_kind:"reading_followup", evidence:"mem_a2", message:"你提到的《思考，快与慢》已读完？要不要我把读书笔记拉成 wiki 页？", delivered:1 },
    { id:"int_03", created_at:"2026-06-28 09:10:00", trigger_kind:"meeting_prep", evidence:"mem_a1,mem_a6", message:"周三与 Lily 见面前，记得带上「用户访谈纪要」。要现在生成一份摘要吗？", delivered:0 },
  ];

  const recommendations = {
    book: [
      { item:"Human Compatible — Stuart Russell", reason:"延续你对 system1/system2 的兴趣到 AI 价值对齐主题。", based_on:["persona:cognition","mem:mem_a2"], from_search:true },
      { item:"From Bacteria to Bach and Back — Daniel Dennett", reason:"与 Kahneman 框架可对话的意识进化视角。", based_on:["mem:mem_a2"], from_search:true },
      { item:"Algorithms to Live By — Christian/Griffiths", reason:"工程师友好的认知决策书，配你的双背景。", based_on:["persona:identity"], from_search:true },
    ],
    movie: [
      { item:"《Her》(2013)", reason:"探讨人与个人 AI 关系，与你正在构建的方向同频。", based_on:["persona:identity"], from_search:true },
      { item:"《降临》(2016)", reason:"语言/认知/时间题材，匹配你阅读偏好。", based_on:["persona:cognition"], from_search:true },
    ],
    action: [
      { item:"为周三会面准备 3 张精简访谈卡", reason:"匹配你「带访谈纪要给 Lily」的意图。", based_on:["mem:mem_a6"], from_search:false },
      { item:"今晚 22:00 前关闭工作群通知", reason:"你偏好安静环境，且明早需要早起喂药。", based_on:["mem:mem_a5","mem:mem_a3"], from_search:false },
    ],
  };

  const wikiPages = [
    { id:"wiki_reading", title:"2026 阅读清单", body:"今年的阅读重心在认知科学与系统论：已完成《思考，快与慢》（Kahneman），下一本候选《Human Compatible》。每读完一本同步写读书笔记并互链到「认知 / 决策」。", tags:"阅读,认知,清单", source_ids:"mem_a2,mem_a5", link_ids:"wiki_cognition", created_at:"2026-06-28 09:43:05" },
    { id:"wiki_cognition", title:"认知 / 决策", body:"个人决策框架：双系统模型 + prospect theory + 反幻觉自检；典型陷阱：anchor / availability / sunk cost。", tags:"认知,决策,框架", source_ids:"mem_a2", link_ids:"wiki_reading,wiki_pets", created_at:"2026-06-20 11:10:00" },
    { id:"wiki_pets",      title:"小奶猫·健康档案",  body:"3 月龄，体重 1.2kg；当前疗程：广谱抗生素剂量减半，连续 3 天，早 9:00 用药。", tags:"宠物,健康", source_ids:"mem_a3", link_ids:"", created_at:"2026-06-27 22:48:30" },
    { id:"wiki_okr", title:"2026Q3 OKR", body:"O1 完成数字分身 v1（含反幻觉与溯源）；O2 输出隐私优先数据脱敏方案并通过法务；O3 重建个人 wiki 增量构建。", tags:"工作,OKR", source_ids:"mem_a4,mem_a6", link_ids:"wiki_cognition", created_at:"2026-06-15 10:00:00" },
  ];

  const verifyReport = {
    status:"partial",
    passed: 18, failed: 2, warned: 3, total: 23,
    items: [
      { id:"v1", kind:"when_dt 重解一致", target:"evt_01", expected:"2026-07-01 15:00", actual:"2026-07-01 15:00", status:"passed" },
      { id:"v2", kind:"when_dt 重解一致", target:"evt_02", expected:"2026-07-03 18:00", actual:"2026-07-03 18:00", status:"passed" },
      { id:"v3", kind:"事件来源落地", target:"evt_03", expected:"seg_3f9a05 含 \"明天早上喂药\"", actual:"命中", status:"passed" },
      { id:"v4", kind:"记忆 evidence 落地", target:"mem_a7", expected:"非空", actual:"为空", status:"failed", hint:"该 emotion 记忆未挂 evidence，可能为蒸馏产物，建议人工核查" },
      { id:"v5", kind:"wiki 源记忆存在", target:"wiki_reading", expected:"mem_a2,mem_a5 存在", actual:"全部命中", status:"passed" },
      { id:"v6", kind:"推荐落地", target:"recommend:book[0]", expected:"item 落地联网搜索", actual:"命中维基百科", status:"passed" },
      { id:"v7", kind:"chat 引用记忆", target:"chat:#2", expected:"mem_a2 存在", actual:"命中", status:"passed" },
      { id:"v8", kind:"persona 维度落地", target:"profile.emotionalStyle", expected:"evidence 不为空", actual:"仅 1 条且弱", status:"warned" },
      { id:"v9", kind:"提醒来源落地", target:"rmd_04", expected:"source_segment 存在", actual:"为空（定时类）", status:"warned" },
      { id:"v10", kind:"事件未来时序", target:"evt_03", expected:"when_dt > now()", actual:"通过", status:"passed" },
    ],
  };

  const health = {
    api: "running",
    llm: "openai_compat · GLM-4.6",
    asr: "whisper-large-v3 (device)",
    embedder: "bge-m3-zh",
    speaker: "TextDiarizer (heuristic)",
    inbox: 3,
    db: "SQLite 142 MB",
    latency_ms: 184,
  };

  return { segments, memories, events, reminders, chatLog, speakers, persona, interventions, recommendations, wikiPages, verifyReport, health };
})();

Object.assign(window, { MockData });
