/**
 * 中文标签与解释层。
 *
 * 界面上不允许裸奔英文术语：每个指标/维度/枚举都要有中文名 + 一句话"怎么读"。
 * 解释只说"这个数高/低意味着什么、单位是什么"，不夸大效度；效度限制由
 * portrait-bits 的 is_proxy / eligible / 未升格说明承担。
 */

/** 过时阈值（与 memcore/profile.py 的常量保持一致） */
export const STALE_GOAL_DAYS = 90;
export const STALE_TASK_DAYS = 60;

export interface MetricZh {
  zh: string;
  explain: string;
}

/** 19 项复杂科学指标：中文名 + 怎么读 */
export const METRIC_ZH: Record<string, MetricZh> = {
  signature_shares: {
    zh: "社交签名份额",
    explain: "把你联系的人按消息量排序后每人占的份额。曲线越陡=注意力越集中在少数人；越平=撒得越开。",
  },
  dunbar_layers: {
    zh: "邓巴分层断点",
    explain: "在份额曲线上自动找断点分出的亲疏层数与每层人数。不是硬套 5/15/50/150，是你自己的实际圈层。",
  },
  social_entropy: {
    zh: "社交熵",
    explain: "联系人的分散程度（香农熵）。高=跟很多人都聊一点；低=只跟固定几个人聊。",
  },
  burstiness_global: {
    zh: "全局爆发度",
    explain: "发消息间隔的爆发程度，-1 到 1。接近 0=像钟表一样均匀；接近 1=一阵猛聊然后长时间沉默。已先剔除昼夜与星期节律。",
  },
  burstiness_person: {
    zh: "对单人的爆发度",
    explain: "只对某一个人的聊天间隔爆发程度。样本不足 50 条不出数。",
  },
  inter_event_alpha: {
    zh: "间隔幂律指数",
    explain: "间隔分布尾部的厚度（α）。α 小=偶尔出现极长沉默；α 大=间隔比较规整。与对数正态做过判别。",
  },
  circadian_strength: {
    zh: "昼夜节律强度",
    explain: "24 小时作息的规律程度，0 到 1。高=每天固定时段活跃；低=昼夜不分。",
  },
  weekly_rhythm: {
    zh: "星期节律",
    explain: "一周七天的分布差异与工作日/周末比。看你是工作驱动还是周末驱动。",
  },
  contact_diversity: {
    zh: "联系人多样性",
    explain: "每周活跃联系人数目的熵。高=那周见的人杂；低=那周只跟固定的人说话。",
  },
  topic_entropy: {
    zh: "话题熵",
    explain: "聊天话题的分散程度（词频熵代理）。高=聊得杂；低=反复聊少数几件事。",
  },
  attention_zipf: {
    zh: "注意力 Zipf 指数",
    explain: "话题/人物频次的秩-频斜率。越陡=注意力越集中在头部少数项。做过对数正态判别，不看见长尾就断言幂律。",
  },
  ews_autocorr: {
    zh: "早期预警自相关",
    explain: "日活跃度与情绪序列的 lag-1 自相关和方差趋势。升高可能预示状态转折（临界慢化）；需 ≥100 天日样本，不足不出数。",
  },
  dfa_alpha: {
    zh: "长程波动指数",
    explain: "去趋势波动分析的 α。≈0.5=白噪声无记忆；≈1=有长程记忆（今天的状态影响很久以后）。需 ≥512 个日样本，不足一律不出数。",
  },
  permutation_entropy: {
    zh: "排列熵",
    explain: "日序列形态的不可预测程度。高=每天的起伏模式杂乱；低=起伏模式重复。",
  },
  sample_entropy: {
    zh: "样本熵",
    explain: "序列的规律性（越小越规律）。与排列熵互为印证。",
  },
  rqa: {
    zh: "递归定量分析",
    explain: "把每天的多维状态（消息数/人数/情绪/话题熵）画成递归图：DET 高=生活模式重复可预测；ENTR 高=模式复杂多变；Lmax 小=对扰动敏感。",
  },
  hmm_states: {
    zh: "隐状态数",
    explain: "用隐马尔可夫模型自动分出你处于几种生活状态（如高压/平稳/社交活跃），以及状态间怎么切换。状态数由 BIC 自动选。",
  },
  cooccurrence_network: {
    zh: "共现网络结构",
    explain: "在同一场对话里共同出现的人连成图：节点数/密度/聚类/模块度。看你的社交圈是几个互不相通的圈子还是一张网。",
  },
  multiplex_pagerank: {
    zh: "多层重要度",
    explain: "把微信文字/群聊/语音当作多层网络，算跨层的重要度排名。谁在你的多层关系里都靠中心。",
  },
};

/** 特质维度的中文解释（怎么读 mean 的正负） */
export const DIM_EXPLAIN: Record<string, string> = {
  ipc_agency: "正=在这段关系里更主导、拿主意；负=更顺从、配合。",
  ipc_communion: "正=更温暖、主动靠近；负=更疏离、保持距离。",
  attach_anxiety: "高=更怕被放下、需要反复确认；低=对关系更安心。",
  attach_avoidance: "高=更回避亲密、不愿求助；低=愿意靠近和依赖。",
  big5_N: "高=更容易紧张、担忧、情绪起伏；低=更平稳。",
  big5_E: "高=更外向、主动社交；低=更安静、独处充电。",
  big5_O: "高=更爱新经验与新想法；低=更偏好熟悉与确定。",
  big5_A: "高=更信任、体谅、合作；低=更质疑、竞争。",
  big5_C: "高=更有条理、守承诺、按计划；低=更随性。",
};

export const TASK_TYPE_ZH: Record<string, string> = {
  next_action: "下一步行动",
  project: "多步项目",
  waiting_for: "等别人",
  tickler: "到时提醒",
  someday_maybe: "以后也许",
  reference: "参考资料",
};

export const ALIAS_SPACE_ZH: Record<string, string> = {
  wxid: "微信号",
  nickname: "昵称",
  remark: "备注名",
  group_card: "群名片",
  speaker_tag: "发言标签",
  chat_id: "会话 ID",
  placeholder: "导出占位符",
};

export const PERSON_KIND_ZH: Record<string, string> = {
  self: "本人",
  person: "人物",
  official: "公众号",
  bot: "系统会话",
  unknown: "群内占位",
};

export const SCHWARTZ_ZH: Record<string, string> = {
  self_direction: "自主方向",
  stimulation: "刺激新鲜",
  hedonism: "享乐",
  achievement: "成就",
  power: "权力支配",
  security: "安全",
  conformity: "遵从",
  tradition: "传统",
  benevolence: "仁爱",
  universalism: "普世关怀",
};

export const GROWTH_ZH: Record<string, string> = {
  autonomy: "自主（按自己的标准行事）",
  env_mastery: "环境掌控（把生活安排得动）",
  personal_growth: "持续成长（愿意学新东西）",
  positive_relations: "关系质量（有温暖信任的关系）",
  purpose: "生活目标感",
  self_acceptance: "自我接纳（接纳自己的过去）",
};

export const SOURCE_ZH: Record<string, string> = {
  fts: "全文",
  vec: "向量",
};

export const LEVEL_ZH: Record<string, string> = {
  runway: "下一步",
  project: "项目",
  area: "责任领域",
  goal_1_2y: "1–2 年目标",
  vision_3_5y: "3–5 年愿景",
  purpose: "目的",
};
