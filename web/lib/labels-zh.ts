/**
 * 中文标签与解释层。
 *
 * 界面上不允许裸奔英文术语，也不允许裸奔数字：每个指标都要回答三件事——
 *   purpose  这个指标用来干啥（一句话）
 *   high     数字高意味着什么
 *   low      数字低意味着什么
 * 以及"高还是低"的判据：观测值对比**随机打乱基线**（null_mean）与 p 值，
 * 而不是拍一个绝对阈值——复杂科学指标没有普适的"正常范围"，
 * 唯一可靠的参照是"比你自己的随机打乱版本高多少"。
 */

/** 过时阈值（与 memcore/profile.py 的常量保持一致） */
export const STALE_GOAL_DAYS = 90;
export const STALE_TASK_DAYS = 60;

export interface MetricZh {
  zh: string;
  purpose: string;
  high: string;
  low: string;
}

/** 19 项复杂科学指标 */
export const METRIC_ZH: Record<string, MetricZh> = {
  signature_shares: {
    zh: "社交签名份额",
    purpose: "看你的注意力怎么分给不同的人：把联系的人按消息量排序，每人占多少份额。",
    high: "曲线陡=注意力集中在少数几个人身上。",
    low: "曲线平=撒得开，跟很多人都聊一点。",
  },
  dunbar_layers: {
    zh: "邓巴分层断点",
    purpose: "自动在你的份额曲线上找断点，分出亲疏圈层（不是硬套 5/15/50/150）。",
    high: "层数多=你的社交结构分层清晰。",
    low: "层数少=圈层模糊，大家差不多远近。",
  },
  social_entropy: {
    zh: "社交熵",
    purpose: "联系人的分散程度：你是跟固定几个人聊，还是跟很多人都聊一点。",
    high: "分散，跟很多人都聊一点。",
    low: "集中，只跟固定几个人聊。",
  },
  burstiness_global: {
    zh: "全局爆发度",
    purpose: "你发消息的节奏：是均匀细水长流，还是一阵猛聊然后长时间沉默。",
    high: "接近 1=爆发式（一阵猛聊后长沉默）。",
    low: "接近 -1=非常均匀；0=泊松随机。已先剔除昼夜与星期节律。",
  },
  burstiness_person: {
    zh: "对单人的爆发度",
    purpose: "只对某一个人的聊天节奏：是稳定联系还是忽冷忽热。",
    high: "对这个人忽冷忽热、一阵一阵。",
    low: "对这个人联系节奏稳定。样本不足 50 条不出数。",
  },
  inter_event_alpha: {
    zh: "间隔幂律指数",
    purpose: "聊天间隔分布的尾部厚度：会不会偶尔消失很久。",
    high: "间隔规整，很少长时间消失。",
    low: "尾部厚，偶尔会消失很久。与对数正态做过判别。",
  },
  circadian_strength: {
    zh: "昼夜节律强度",
    purpose: "24 小时作息规律程度：每天是不是固定时段活跃。",
    high: "作息规律，固定时段活跃。",
    low: "昼夜不分，什么时候都聊。",
  },
  weekly_rhythm: {
    zh: "星期节律",
    purpose: "一周七天的分布差异：工作驱动还是周末驱动。",
    high: "weekday/周末差异大，生活有周节奏。",
    low: "七天差不多，没有明显周节奏。",
  },
  contact_diversity: {
    zh: "联系人多样性",
    purpose: "每周活跃联系人数目的变化：那周见的人杂不杂。",
    high: "那周接触的人杂。",
    low: "那周只跟固定的人说话。",
  },
  topic_entropy: {
    zh: "话题熵",
    purpose: "聊天话题的分散程度：聊得杂还是反复聊少数几件事。",
    high: "聊得杂，话题分散。",
    low: "反复聊少数几件事，注意力集中。",
  },
  attention_zipf: {
    zh: "注意力 Zipf 指数",
    purpose: "话题/人物频次的秩-频斜率：注意力是否集中在头部少数项。",
    high: "斜率陡=注意力高度集中在头部少数项。",
    low: "斜率缓=注意力分散。做过对数正态判别，不看见长尾就断言幂律。",
  },
  ews_autocorr: {
    zh: "早期预警自相关",
    purpose: "日活跃度与情绪的 lag-1 自相关和方差趋势：状态是否正在失去弹性（临界慢化），可能预示转折。",
    high: "自相关/方差升高=状态变「黏」、恢复变慢，可能临近转折。",
    low: "状态弹性好，波动后能较快恢复。需 ≥100 天日样本，不足不出数。",
  },
  dfa_alpha: {
    zh: "长程波动指数",
    purpose: "波动有没有长程记忆：今天的状态会不会影响很久以后。",
    high: "≈1=有长程记忆（粉红噪声），状态有延续性。",
    low: "≈0.5=白噪声无记忆，每天独立。需 ≥512 个日样本，不足一律不出数。",
  },
  permutation_entropy: {
    zh: "排列熵",
    purpose: "日序列起伏模式的不可预测程度。",
    high: "起伏模式杂乱、不可预测。",
    low: "起伏模式重复、可预测。",
  },
  sample_entropy: {
    zh: "样本熵",
    purpose: "序列的规律性，与排列熵互为印证。",
    high: "规律性低，序列复杂。",
    low: "规律性高，序列重复。",
  },
  rqa: {
    zh: "递归定量分析",
    purpose: "把每天的多维状态（消息数/人数/情绪/话题熵）画成递归图，看你的生活模式是重复可预测还是复杂多变。下面展开四个子量。",
    high: "见各子量：DET 高=模式重复可预测；RR 高=常回到相似状态。",
    low: "ENTR 高=模式复杂多变；Lmax 小=对扰动敏感。",
  },
  hmm_states: {
    zh: "隐状态数",
    purpose: "用隐马尔可夫模型自动分出你处于几种生活状态（如高压/平稳/社交活跃），以及状态间怎么切换。",
    high: "状态数多=生活在多种模式间切换。",
    low: "状态数少=生活模式单一。状态数由 BIC 自动选。",
  },
  cooccurrence_network: {
    zh: "共现网络结构",
    purpose: "在同一场对话里共同出现的人连成图：你的社交圈是几个互不相通的圈子还是一张网。",
    high: "模块度/聚类高=圈子之间互不相通。",
    low: "圈子互相连通，是一张网。",
  },
  multiplex_pagerank: {
    zh: "多层重要度",
    purpose: "把微信文字/群聊/语音当作多层网络，算跨层重要度：谁在你的多层关系里都靠中心。",
    high: "某人在多层里都靠中心=跨场景都重要。",
    low: "只在单一场景出现。",
  },
};

/** RQA 四个子量：各自的高/低含义。观测值对比随机打乱基线才有意义。 */
export const RQA_SUB: Record<string, MetricZh> = {
  RR: {
    zh: "递归率 RR",
    purpose: "有多少比例的日子，你的状态和过去某个日子相似。",
    high: "常回到相似状态，生活有重复性。",
    low: "很少重复，每天都不一样。",
  },
  DET: {
    zh: "决定论度 DET",
    purpose: "相似状态会不会连成串（连续几天同一种状态）：模式是否可预测。",
    high: "状态成串延续，模式可预测、决定论强。",
    low: "状态跳来跳去，不成串。",
  },
  ENTR: {
    zh: "对角线熵 ENTR",
    purpose: "对角线长度分布的复杂程度：状态延续的时长是单一还是多样。",
    high: "延续时长多样，模式复杂多变。",
    low: "延续时长单一，模式简单。",
  },
  Lmax: {
    zh: "最长对角线 Lmax",
    purpose: "最长的一段「状态稳定期」有多长：对扰动的敏感度。",
    high: "有很长的稳定期，抗扰动。",
    low: "稳定期短，对扰动敏感。",
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

/** 复杂度指标 tab 的开场白：这些指标是干啥的 */
export const METRICS_INTRO =
  "这一页回答一个问题：你的生活与关系**模式**长什么样——不是诊断，也不是评分。" +
  "每个数字都配了三样东西：用来干啥、高意味着什么、低意味着什么；" +
  "以及它对比**你自己随机打乱后**的基线高多少（p 值）——复杂科学指标没有普适的「正常范围」，" +
  "唯一可靠的参照是你自己的随机版本。样本不足的指标灰显并说明缺什么，不编数字。";
