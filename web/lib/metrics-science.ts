/**
 * 「指标科普」整版内容单一真源。
 *
 * 每个指标回答五件事：从哪来（论文/作者/年份）、直觉上量的是什么、公式长什么样、
 * 怎么读（图与数）、效度如何评估（置换基线怎么造 / CI 怎么算 / 出数门槛 / 已知局限）。
 * 全部内容与 memcore/metrics.py 的实现同源：出处取自代码内的引用注释，
 * 门槛与基线构造取自 GATE_ZH 与 null_block 的实参，不写代码里没有的东西。
 *
 * 这里**不放任何你的数字**——科普页只讲方法；你的数值在「复杂度指标」tab。
 */

export type ScienceGroupId =
  | "rhythm" | "social" | "dynamics" | "language" | "network";

export interface MetricScience {
  zh: string;
  group: ScienceGroupId;
  /** 出处：作者 年份 期刊/会议 */
  origin: string;
  /** 直觉：这个量在量什么 */
  intuition: string;
  /** 公式（纯文本，不渲染 LaTeX） */
  formula?: string;
  /** 怎么读：界面上的图与数分别看什么 */
  read: string;
  validity: {
    /** 随机基线（零假设）是怎么造出来的、置换几次、单侧还是双侧 */
    null_kind: string;
    /** 置信区间怎么算 */
    ci_method: string;
    /** 出数门槛：不到就灰显给理由，不编数 */
    gate: string;
    /** 已知局限 */
    limits: string;
  };
  caveats?: string;
}

export const SCIENCE_GROUPS: { id: ScienceGroupId; zh: string; blurb: string }[] = [
  { id: "rhythm", zh: "时间节律", blurb: "你的行为在时间轴上的形状：什么时候聊、一阵还是一直、会不会消失很久。" },
  { id: "social", zh: "社交结构", blurb: "注意力在人与人之间怎么分配：签名、圈层、分散程度。" },
  { id: "dynamics", zh: "复杂动力学", blurb: "把每天的状态看成一条动力轨迹：有没有记忆、有没有重复模式、有没有临近转折的信号。" },
  { id: "language", zh: "语言与内容", blurb: "聊什么、注意力是否集中在头部少数话题。" },
  { id: "network", zh: "网络", blurb: "把人当成节点：你的社交圈是几个互不相通的圈子，还是一张跨场景的网。" },
];

export const METRICS_SCIENCE: Record<string, MetricScience> = {
  // ── 时间节律 ────────────────────────────────────────────────
  circadian_strength: {
    zh: "昼夜节律强度",
    group: "rhythm",
    origin: "经典昼夜/作息熵度量；实现见 metrics.py m_circadian_strength",
    intuition: "把一天 24 小时的消息数看成一个分布：越集中在固定时段，分布熵越低，节律越强。",
    formula: "strength = 1 − H(24 小时直方图) / ln 24",
    read: "24 根柱是你的小时分布；朱砂线是圆形均值作息点。强度接近 1=固定时段活跃，接近 0=昼夜不分。",
    validity: {
      null_kind: "日内时钟置换（小时均匀打乱）600 次，单侧 greater",
      ci_method: "删一天折刀（delete-one-day jackknife）",
      gate: "消息 ≥200 且 天数 ≥20",
      limits: "只量「集中在哪些小时」，不区分主动作息与被动加班；轮班/跨时区旅行会把它拉低。",
    },
  },
  weekly_rhythm: {
    zh: "工作日/周末比值",
    group: "rhythm",
    origin: "描述性节律量；星期熵部分同 circadian 思路",
    intuition: "工作日日均消息量除以周末日均：你的社交是工作驱动还是生活驱动。",
    formula: "ratio = 工作日日均 / 周末日均；dow_strength = 1 − H(7 星期直方图)/ln 7",
    read: "7 根柱靛青=工作日、赭石=周末，两条虚线是各自均值。>1 工作日驱动，<1 周末驱动，≈1 无差异；极端值（如 34）=周末基本沉默。",
    validity: {
      null_kind: "整天置换（day_permute，星期标签按原下标保留）2000 次，双侧",
      ci_method: "删一周折刀（fold=7 天）",
      gate: "消息 ≥200 且 天数 ≥28；周末日均为 0 直接拒（比值无穷大不可解释）",
      limits: "节假日调休会污染「工作日/周末」标签；自由职业者该量本身语义弱。",
    },
  },
  burstiness_global: {
    zh: "全局爆发度",
    group: "rhythm",
    origin: "Goh & Barabási 2008（EPL, burstiness 系数定义）",
    intuition: "发消息间隔是均匀细水长流，还是一阵猛聊后长沉默。必须先剔除昼夜与星期节律，否则「白天聊晚上睡」会被误读成爆发。",
    formula: "B = (σ_τ − μ_τ) / (σ_τ + μ_τ)，τ 为**操作时间**（time-rescaling 剔除周期后）的间隔",
    read: "森林图里朱砂点落在灰带（你的随机基线）右侧=比「同作息的随机版本」更爆发。B→1 一阵一阵，B→−1 极均匀，0=泊松随机。",
    validity: {
      null_kind: "日内操作时间置换并重校准（保留每日消息数、按未收缩的小时剖面重抽时刻、重跑收缩管线）400 次，单侧 greater",
      ci_method: "删一天折刀",
      gate: "消息 ≥100",
      limits: "操作时间收缩依赖小时/星期剖面估计，样本稀时剖面本身不稳；长假/生病造成的沉默与「爆发性格」不可区分。",
    },
    caveats: "这是**剔除节律后**的爆发度；与原始时钟上的 B 不同，界面上另给 B_raw_clock 供对照。",
  },
  burstiness_person: {
    zh: "对单人的爆发度",
    group: "rhythm",
    origin: "Goh & Barabási 2008 的按对象分解版",
    intuition: "只对某一个人的聊天节奏：是稳定联系还是忽冷忽热。headline 是合格对象的中位数 B。",
    formula: "headline = median{ B_u : 对象 u 消息 ≥50 }",
    read: "高=对多数人忽冷忽热；低=对多数人节奏稳定。子量里有合格对象数与 B 的四分位。",
    validity: {
      null_kind: "重校准置换后把操作时间按「对象×天」观测数发牌 400 次，单侧 greater",
      ci_method: "对对象重抽样 bootstrap 80 次",
      gate: "合格对象 ≥3（每个对象消息 ≥50）",
      limits: "中位数掩盖个体差异：可能对某人极爆发、对某人极稳定，headline 看不出来。",
    },
  },
  inter_event_alpha: {
    zh: "间隔幂律指数",
    group: "rhythm",
    origin: "Clauset–Shalizi–Newman 2009（幂律拟合与 KS 选 x_min）；对数正态判别用 Vuong 1989",
    intuition: "聊天间隔分布的尾部厚度：你会不会偶尔消失很久。α 小=尾厚=常有长沉默。",
    formula: "α = 1 + n / Σ ln(x_i / x_min)，x_min 由 KS 最小化选出；再与截断对数正态做 Vuong 似然比",
    read: "α 高=间隔规整、很少长消失；α 低=尾部厚。子量里的 lr_verdict 会明说「幂律 / 对数正态 / 不可区分」——不可区分时不得声称幂律。",
    validity: {
      null_kind: "日内时钟置换 400 次，双侧；每个 surrogate 在**观测的 x_min** 上重算 α（条件推断）",
      ci_method: "删一天折刀",
      gate: "消息 ≥200（τ≥1s）且 尾部样本 ≥50",
      limits: "幂律与对数正态在有限样本下经常不可区分；x_min 选择对 α 敏感。",
    },
  },

  // ── 社交结构 ────────────────────────────────────────────────
  signature_shares: {
    zh: "社交签名·top1 份额",
    group: "social",
    origin: "Saramäki et al. 2014 PNAS（社交签名的持久性）",
    intuition: "把你的通信量按对象排序取份额向量：每个人拿走的注意力比例。headline 是 top1 份额。",
    formula: "p_i = n_i / Σ_j n_j；headline = p_(1)；另给 p_top5 / gini / HHI / 归一化熵",
    read: "top20 柱状图看形状（陡=集中）；森林图看 top1 份额是否高于「均匀分配」的随机基线。",
    validity: {
      null_kind: "均匀多项分配 Multinomial(total, 1/M) 2000 次，单侧 greater",
      ci_method: "多项 bootstrap 百分位",
      gate: "消息 ≥200 且 合格对象 ≥10",
      limits: "只量消息量不量情感强度；群与公众号会被当成「对象」，订阅号推送会扭曲份额。",
    },
    caveats: "子量里的 signature_stability_spearman 是前半段 vs 后半段秩相关：它低说明签名本身在漂移，headline 只是两段混合。",
  },
  dunbar_layers: {
    zh: "邓巴分层断点",
    group: "social",
    origin: "变点检测：Killick, Fearnhead & Eckley 2012 JASA（PELT）；分层思想源自 Dunbar 的圈层假设但**不硬套 5/15/50/150**",
    intuition: "在秩-份额曲线上自动找断点：你的关系自然分成几层亲疏圈。",
    formula: "PELT + Gaussian L2 cost，惩罚 β=2σ̂²ln n（σ̂ 取自一阶差的 MAD），min_seg=2",
    read: "柱状图每圈=一层（柱高人数、标注份额）；断点秩在注里。层数多=结构分层清晰。",
    validity: {
      null_kind: "均匀多项分配后对每个 surrogate 跑 PELT 数层数，500 次，**双侧**（真实签名更平滑、层数更少，方向非先验）",
      ci_method: "多项 bootstrap 对层数 k",
      gate: "消息 ≥200 且 合格对象 ≥12",
      limits: "1 层=检不出断点，不等于「没有圈层」；断点位置对噪声敏感，CI 可能很宽。",
    },
  },
  social_entropy: {
    zh: "社交熵",
    group: "social",
    origin: "Tadić 2012（通信熵）；层内/层间分解为本实现自带",
    intuition: "联系人的分散程度：跟固定几个人聊，还是跟很多人都聊一点。",
    formula: "H_global = −Σ p ln p；H = H_within(层内加权) + H_between(层间份额熵)",
    read: "整条堆叠条=100% 消息在圈层间的分配；注里给三个熵分量。H 高=分散，低=集中。",
    validity: {
      null_kind: "均匀多项分配 2000 次，单侧 **less**（真实社交比均匀分配更集中，熵更低）",
      ci_method: "删一事件折刀（J=10 折）",
      gate: "消息 ≥200 且 合格对象 ≥8",
      limits: "熵对对象数 M 敏感：M 变大熵自然变大，跨人比较时要看归一化 H_norm。",
    },
  },
  contact_diversity: {
    zh: "联系人多样性",
    group: "rhythm",
    origin: "滑动窗 Shannon 熵的周聚合（描述性量）",
    intuition: "每周活跃联系人数目的变化：那周见的人杂不杂。",
    formula: "headline = mean_week{ H(该周每联系人消息数) }（nat）",
    read: "高=那周接触的人杂；低=只跟固定的人说话。森林图看它是否偏离「整天置换」基线。",
    validity: {
      null_kind: "整天置换（整日搬移、保留日内联系人集合）600 次，双侧",
      ci_method: "删一周折刀",
      gate: "消息 ≥100 且 有效周 ≥12",
      limits: "每周熵的序列**没有存进库**，界面只给均值与 sd，看不到哪周突变。",
    },
  },

  // ── 复杂动力学 ──────────────────────────────────────────────
  ews_autocorr: {
    zh: "早期预警自相关",
    group: "dynamics",
    origin: "van de Leemput et al. 2014 PNAS（临界慢化作为心理转折的早期预警）",
    intuition: "系统临近转折时会「失去弹性」：波动恢复变慢，表现为 lag-1 自相关与方差随时间上升（临界慢化）。",
    formula: "对滚动窗（w=max(20, N/10)）的日消息量 lag-1 自相关与方差，取 Kendall τ_b 趋势",
    read: "headline 是 τ_b 趋势：正=自相关/方差在升高=状态变「黏」。子量分 activity 与情绪代理两支。**弱证据，不得当成诊断。**",
    validity: {
      null_kind: "整天置换 2000 次，单侧 greater",
      ci_method: "删一天折刀",
      gate: "天数 ≥100（原论文要求每日多次、连续数月的密集采样；日样本不足时假阳性极高）",
      limits: "聊天量≠心理状态；生活事件（换工作、旅行）同样造成自相关上升。滚动窗序列未存库。",
    },
    caveats: "原论文用的是**每日多次**的经验采样（ESM）；这里只有日消息量，是降级代理，解释力远弱于原文。",
  },
  dfa_alpha: {
    zh: "长程波动指数",
    group: "dynamics",
    origin: "Peng et al. 1994（DFA, 去趋势波动分析）",
    intuition: "波动有没有长程记忆：今天的状态会不会影响很久以后。",
    formula: "F(n) = 累积偏差剖面在尺度 n 上窗内线性去趋势后的 RMS；log-log 斜率 = α",
    read: "双对数曲线（点=实测 12 个尺度）；α≈0.5 白噪声无记忆，≈1 粉红噪声有长程记忆，>1.5 非平稳。",
    validity: {
      null_kind: "整天置换 400 次（置换后期望 α≈0.5），单侧 greater",
      ci_method: "删一天折刀",
      gate: "天数 ≥512（DFA 的硬要求；当前 362 天，故灰显）",
      limits: "样本不足时 α 估计方差极大；周期成分（星期节律）会在特定尺度造假斜率。",
    },
  },
  permutation_entropy: {
    zh: "排列熵",
    group: "dynamics",
    origin: "Bandt & Pompe 2002（PRL, 排列熵）",
    intuition: "日序列起伏**模式**（升/降/平的顺序词）的不可预测程度。",
    formula: "H(序数模式分布)/ln(m!)，规格钉死 m=2、delay=1；detail 另给 m=3 版",
    read: "高=起伏模式杂乱；低=模式重复可预测。与样本熵互为印证。",
    validity: {
      null_kind: "整天置换 2000 次，双侧",
      ci_method: "删一天折刀",
      gate: "天数 ≥100",
      limits: "m=2 只看到相邻两天的升降，信息量很少；对单调趋势不敏感。",
    },
  },
  sample_entropy: {
    zh: "样本熵",
    group: "dynamics",
    origin: "Richman & Moorman 2000（AJM, SampEn）",
    intuition: "序列的规律性：相似的片段会不会再次出现。与排列熵从不同角度量同一件事。",
    formula: "SampEn = −ln(A/B)，m=2、r=0.2σ、Chebyshev 距离、排除自匹配",
    read: "高=规律性低、序列复杂；低=重复性强。",
    validity: {
      null_kind: "整天置换 200 次，双侧",
      ci_method: "删一天折刀",
      gate: "天数 ≥100；σ=0 或 A=0（SampEn=∞）时拒",
      limits: "r 取 0.2σ 是惯例不是定理；短序列上 SampEn 偏差已知。",
    },
  },
  rqa: {
    zh: "递归定量分析",
    group: "dynamics",
    origin: "Zbilut & Webber（RQA 起源）；Marwan 2007 综述（规格与参数选择）",
    intuition: "把每天的多维状态（消息数/活跃人数/情绪代理/话题熵）画成递归图：生活模式是重复可预测，还是复杂多变。",
    formula: "ε=成对欧氏距离的 5 分位；Theiler=1、lmin=vmin=2；RR/DET/ENTR/Lmax 四子量",
    read: "四个迷你森林图各看一子量：RR 高=常回到相似状态；DET 高=状态成串、可预测；ENTR 高=延续时长多样；Lmax 大=稳定期长、抗扰动。",
    validity: {
      null_kind: "整天置换 250 次，四个子量各给 p 值",
      ci_method: "删一块折刀（J=10）逐子量",
      gate: "天数 ≥100 且 维度 ≥4",
      limits: "规格明确要求对**多元日特征向量**做；嵌入维 1~2 时 DET/ENTR 反映的是聚合方式而不是动力学。完整 null 数组未存库，只存均值与 p。",
    },
  },
  hmm_states: {
    zh: "隐状态数",
    group: "dynamics",
    origin: "经典高斯发射 HMM + Baum–Welch（scaled forward-backward）；模型选择用 BIC",
    intuition: "自动分出你处于几种生活状态（如高压/平稳/社交活跃），以及状态间怎么切换。",
    formula: "k∈{3,4,5}，BIC=−2lnL+p·lnN，p=k(k−1)+2kd+(k−1)；3 次重启、max_iter=60",
    read: "30 格状态条=最近一个月的解码路径；转移矩阵看「今天→明天」概率；BIC 折线看 k 怎么选。状态数多=生活在多种模式间切换。",
    validity: {
      null_kind: "整天置换 30 次，p 算在 loglik(k*) 上（单侧 greater）；k 自身的 null 分布在子量里",
      ci_method: "折刀 k* 池的 min/max（**故意不用 ±1.96se**：k 是离散量，正态区间无意义）",
      gate: "天数 ≥150",
      limits: "k 落在边界（3 或 5）时说明真 k 在搜索范围外，注里会标 k_at_boundary；高斯对角发射假设状态内各维独立。",
    },
  },

  // ── 语言与内容 ──────────────────────────────────────────────
  topic_entropy: {
    zh: "话题熵",
    group: "language",
    origin: "词频 Shannon 熵；**词频代理，不是主题模型**（params 里 is_proxy=true）",
    intuition: "聊天话题的分散程度：聊得杂还是反复聊少数几件事。",
    formula: "H/ln(Veff)，Veff=top-500 二元词表（按天跨步抽样、预算 2 万条消息）",
    read: "top12 高频二元词横条看「最近在聊什么」；熵高=杂，低=注意力集中。",
    validity: {
      null_kind: "词元均匀多项 Multinomial(n_top, 1/Veff) 2000 次，单侧 less",
      ci_method: "删一词元折刀（全部 Veff 词元）",
      gate: "消息 ≥500 且 词元 ≥200",
      limits: "二元词≠话题：「好的好的」这类口头禅会占头部；抽样预算意味着不是全语料。",
    },
  },
  attention_zipf: {
    zh: "注意力 Zipf 指数",
    group: "language",
    origin: "Zipf 秩-频律；幂律判别同 Clauset–Shalizi–Newman 2009 流程",
    intuition: "对象/话题频次的秩-频斜率：注意力是否集中在头部少数项。",
    formula: "freq ∝ rank^(−s)，log-log OLS 斜率 s",
    read: "s 陡=注意力高度集中；缓=分散。子量给 R²、斜率标准误与 CSN 判别结果。",
    validity: {
      null_kind: "均匀多项分配 2000 次，单侧 greater",
      ci_method: "删一对象折刀",
      gate: "消息 ≥300 且 合格对象 ≥30（秩点 <3 直接拒）",
      limits: "log-log OLS 对幂律是粗糙估计（CSN 才是严格法）；看见长尾不等于幂律。",
    },
  },

  // ── 网络 ────────────────────────────────────────────────────
  cooccurrence_network: {
    zh: "共现网络结构",
    group: "network",
    origin: "社区检测：Blondel 2008（Louvain）；零模型：Maslov–Sneppen 度保持重连；结构平衡源自 Heider 平衡理论",
    intuition: "在同一场对话里共同出现的人连成边：你的社交圈是几个互不相通的圈子，还是一张网。",
    formula: "边权 w(a,b)=Σ_conv min(n_a, n_b)；会话限 2..60 人；headline=Louvain 模块度 Q（无权投影）",
    read: "社群规模柱看圈子大小是否悬殊；Q/聚类高=圈子互不相通。子量里的 balance 是带符号三角的平衡占比（符号=时间耦合观测 vs 期望）。",
    validity: {
      null_kind: "度保持重连（Maslov–Sneppen 双交换，3E 次）于无权投影，30 次，单侧 greater；balance 另用符号置换 ≤40 次",
      ci_method: "删一会话折刀",
      gate: "self：自我节点 ≥50 且自我边 ≥100；person/conversation：局部节点 ≥20 且局部边 ≥40",
      limits: "共现≠认识：同群陌生人也会连边；边权公式的期望项实现用 2·n_a·n_b/N_conv（旧公式 2·n_a·n_b/(n_a+n_b) 已证误）。",
    },
  },
  multiplex_pagerank: {
    zh: "多层重要度",
    group: "network",
    origin: "Solà, Romance, Criado & Boccaletti 2013（多层网络 supra-adjacency PageRank）",
    intuition: "把单聊文字/群聊/语音当作三层网络，算跨层重要度：谁在你的多层关系里都靠中心。",
    formula: "supra-adjacency 幂迭代，damping=0.85、层间耦合 D_c=0.5、80 轮、tol=1e-10",
    read: "top10 堆叠横条看每人聚合分与各层贡献。**headline 不是某个人的分数**，而是「耦合 vs 解耦排序」的 Spearman ρ：量层间耦合敏感度。",
    validity: {
      null_kind: "度保持重连（**带权**：权重留在槽位里）每层 3E 次交换，15 次，单侧 greater",
      ci_method: "删一会话折刀",
      gate: "非空层 ≥2 且 节点 ≥30",
      limits: "语音层当前为空（录音只存转写文字）；置换仅 15 次，p 分辨率 1/16≈0.063，p<0.05 几乎不可达——读它要看效应量而非 p。",
    },
  },
};

/** 画像三层（特质 / 情感 / 成长）的方法学说明 */
export const LAYER_SCIENCE: Record<"traits" | "affect" | "growth", MetricScience> = {
  traits: {
    zh: "特质（密度分布）",
    group: "social",
    origin: "Fleeson 2001（Whole Trait Theory：特质是密度分布而非标签）；维度取自 Big Five（Costa & McCrae）、IPC 环状模型（Wiggins 1979）、依恋两维（ECR 传统）",
    intuition: "不给你贴「外向/内向」标签，而是维护每个维度的一条分布曲线：mean=倾向方向，sd=行为离散度，skew=歪向。单次发言只是它的一次抽样。",
    formula: "高斯共轭更新：precision = 1 + Σ|confidence|；mean = Σ(w·x)/precision；sd = √(1/precision)，x=带符号置信度",
    read: "曲线宽=行为不一致，窄=稳定；朱砂线=均值。**n_observations=0 时画的是先验起点（mean=0/sd=1），不是测量结果**——界面会明写「纯先验」。",
    validity: {
      null_kind: "无置换基线（贝叶斯更新量，不做零假设检验）；防过度解读靠升格门",
      ci_method: "sd 即后验标准差（共轭闭式），不另算 CI",
      gate: "升格为稳定特质需 ≥3 个**独立会话**复现（DB 触发器强制）；单次吐槽永不升格",
      limits: "全部 is_proxy=1：从聊天行为代理推断，**不是量表实测**；证据稀疏时曲线主要由先验决定。",
    },
    caveats: "负向维度（依恋焦虑/回避、神经质）的方向靠证据置信度的符号表达；抽取层丢弃方向符号的 bug 已于 2026-09-07 修复，修复前的旧证据全为正。",
  },
  affect: {
    zh: "情感剖面",
    group: "dynamics",
    origin: "情绪惯性：Kuppens 2010；情绪粒度：标签分布熵（granularity 文献传统）；标签集 GoEmotions",
    intuition: "五个量描一条情绪曲线：正/负平均强度、摆幅（MSSD）、自我延续（lag-1 自相关）、分辨细腻度（标签熵）。",
    formula: "inertia = lag-1 自相关；granularity = H(GoEmotions 标签分布)；MSSD = 相邻差均方",
    read: "五根柱各看一量；注里逐量解释。样本 <20 时整块灰显并说明缺什么，不出数。",
    validity: {
      null_kind: "无（描述性剖面）",
      ci_method: "无（点估计）",
      gate: "affect_event ≥20 条才 eligible",
      limits: "GoEmotions 人类标注者间 kappa≈0.24 是天花板；当前全库事件稀疏，多数主体 ineligible 属诚实状态。",
    },
  },
  growth: {
    zh: "成长（Ryff 六维代理）",
    group: "social",
    origin: "Ryff 1989（心理幸福感六维：自主/环境掌控/成长/关系/目标/自我接纳）",
    intuition: "六个维度各给一个 0–1 的**行为代理分**：例如目标感用活跃目标数、成长用价值观复现数代理。",
    formula: "purpose=min(n_goal/10,1)；personal_growth=min(n_value/8,1)；positive_relations=min(pa_mean,1)；self_acceptance=clamp(1−na_mean)；autonomy/env_mastery 无可靠被动信号，恒 0 并标注",
    read: "单窗口时画一条量表条而非趋势线，并注明「单窗口，无趋势可言」。恒 0 的两维是**没有信号**，不是「你不行」。",
    validity: {
      null_kind: "无（代理计分）",
      ci_method: "无",
      gate: "无门槛，但每维都标 is_proxy",
      limits: "代理与构念距离很远：目标数多≠目标感强；positive_relations/self_acceptance 依赖情感剖面，情感 ineligible 时它们退化为 0/1。",
    },
  },
};

/** 开头五张诚实规则卡 */
export const HONESTY_RULES: { title: string; body: string }[] = [
  {
    title: "代理，不是量表",
    body: "所有人格/幸福感构念都从聊天行为代理推断（is_proxy=1），没有做过任何自评量表。它们描述「行为看起来像什么」，不诊断「你是什么」。",
  },
  {
    title: "参照系是你自己的随机版本",
    body: "复杂科学指标没有普适「正常范围」。每个 eligible 指标都配一个零假设基线：把你的数据按某种方式打乱重算几百到几千次，看观测值落在打乱分布的哪里。p<0.05 才说「结构真实存在」，否则明写「与随机无异，别当结论」。",
  },
  {
    title: "样本不足就灰显",
    body: "每个指标有出数门槛（消息数/天数/对象数/尾部样本）。不到门槛一律 eligible=0、灰显并说明缺什么——宁可空着，不编一个看起来专业的数字。",
  },
  {
    title: "过时与升格两道门",
    body: "目标 90 天、待办 60 天不活跃即标过时、划线弱化，不再当现状复述；特质需 ≥3 个独立会话复现才升格为稳定特质，单次吐槽永远只是证据不是结论。",
  },
  {
    title: "「你的数怎么读」只是解读扶手",
    body: "每个数字旁的当前解读按该指标的自然量程分档（爆发度 ∈[−1,1]、归一化熵 ∈[0,1]、比值以 1 为界…），再叠加与你随机基线带的位置关系。分档是帮你看懂量级的扶手，不是统计门槛：真正的门槛是出数 gate 与置换检验 p 值；落在基线带内时解读会明说「别当结论」。",
  },
];
