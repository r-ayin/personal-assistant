/**
 * 「你的数怎么读」层。
 *
 * METRIC_ZH 只回答"高意味着什么 / 低意味着什么"（量表语义），用户看到的仍是一串
 * 不知道落在哪里的数字。这里把**观测值本身**翻译成一句人话：
 *   1. 按该指标的自然量程分档（爆发度 ∈[-1,1]、熵归一 ∈[0,1]、比值以 1 为界…）；
 *   2. 再叠加与"你自己的随机打乱基线"的位置关系（高于带上缘 / 带内 / 低于带下缘），
 *      带内就明说"这个结构不能当结论"——复杂科学指标没有普适正常范围。
 * 分档阈值是**解读用的经验分档**，不是统计门槛；统计门槛在 metrics.py 的 gate 里，
 * 不到门槛根本不出数（eligible=0），所以这里拿到的 value 一定是过了门槛的。
 */

export interface NullInfo {
  p_value?: number | null;
  null_mean?: number | null;
  null_q025?: number | null;
  null_q975?: number | null;
}

const band = (v: number, cuts: number[][] | null, labels: string[]): string => {
  // cuts: 升序上界列表（调用处写作 [[a],[b]] 形式），labels 长度 = cuts.length + 1
  if (!cuts) return labels[0];
  for (let i = 0; i < cuts.length; i++) {
    if (v < cuts[i][0]) return labels[i];
  }
  return labels[labels.length - 1];
};

/** 与随机基线带的位置关系 + p 值结论，拼成一句 */
function nullSentence(v: number, nb: NullInfo | null): string {
  if (!nb) return "";
  const lo = nb.null_q025;
  const hi = nb.null_q975;
  const p = nb.p_value;
  let pos = "";
  if (typeof lo === "number" && typeof hi === "number" && lo !== hi) {
    pos = v > hi ? "高于你自己随机基线的 95% 带上缘"
      : v < lo ? "低于你自己随机基线的 95% 带下缘"
        : "落在你自己随机基线的 95% 带内";
  }
  const sig = typeof p === "number" && p < 0.05;
  if (!pos) return sig ? "且 p<0.05，结构真实存在。" : "p≥0.05，别当结论。";
  return sig
    ? `${pos}（p=${p.toFixed(3)}），这个结构不是随机能造出来的。`
    : `${pos}（p=${p == null ? "—" : p.toFixed(3)}），与随机无异，别当结论。`;
}

const f = (v: number, d = 2) => v.toFixed(d);

/** 每个指标：把观测值翻成一句"你现在在哪一档" */
export function interpretMetric(
  name: string,
  value: number | null,
  nb: NullInfo | null,
  detail?: Record<string, any> | null,
): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  const d = detail ?? {};
  let scale = "";
  switch (name) {
    case "signature_shares":
      scale = band(value, [[0.15], [0.35]], [
        `top1 只占 ${f(value * 100, 1)}%：注意力撒得开，没有单一主导对象`,
        `top1 占 ${f(value * 100, 1)}%：有一个明显主对象，但不独占你的注意力`,
        `top1 占 ${f(value * 100, 1)}%：注意力高度集中在一个人身上`,
      ]);
      if (typeof d.p_top5 === "number") scale += `；top5 合计 ${f(d.p_top5 * 100, 1)}%`;
      break;
    case "dunbar_layers":
      scale = value <= 1
        ? "只检出 1 层：份额曲线太滑、找不到断点，圈层模糊（不等于没有圈层）"
        : value <= 3
          ? `检出 ${value} 层：亲疏分层较少，大家差不多远近`
          : value <= 5
            ? `检出 ${value} 层：亲疏分层清晰`
            : `检出 ${value} 层：分层很细，圈层边界多`;
      break;
    case "social_entropy":
      scale = band(typeof d.H_norm === "number" ? d.H_norm : value, [[0.5], [0.8]], [
        "归一化熵偏低：只跟固定几个人聊",
        "归一化熵中等：核心圈子外加一些散联系",
        "归一化熵偏高：跟很多人都聊一点",
      ]);
      break;
    case "burstiness_global":
    case "burstiness_person":
      scale = band(value, [[-0.2], [0.2], [0.6]], [
        "比泊松随机还均匀：细水长流、节奏极稳",
        "接近泊松随机：没有明显的阵发",
        "中等爆发：有一阵一阵的聊天，但不至于长沉默",
        "强爆发式：一阵猛聊之后长时间沉默",
      ]);
      if (name === "burstiness_person") scale = `对多数人的节奏：${scale}`;
      break;
    case "inter_event_alpha":
      scale = band(value, [[1.5], [2.0]], [
        "间隔分布尾厚：你会偶尔消失很久",
        "尾部中等：偶尔有长间隔",
        "间隔规整：很少长时间消失",
      ]);
      if (d.lr_verdict && d.lr_verdict !== "n/a") scale += `；与对数正态判别：${d.lr_verdict === "indistinguishable" ? "不可区分（不得声称幂律）" : d.lr_verdict}`;
      break;
    case "circadian_strength":
      scale = band(value, [[0.2], [0.5]], [
        "昼夜不分：什么时候都聊",
        "作息中等规律：有偏好时段但不严格",
        "作息很规律：固定时段活跃",
      ]);
      if (typeof d.chronotype_hour === "number") scale += `；你的圆形均值作息点在 ${f(d.chronotype_hour, 1)} 时`;
      break;
    case "weekly_rhythm":
      scale = band(value, [[0.8], [1.2], [2.0]], [
        "周末驱动：周末聊得明显更多",
        "工作日与周末几乎无差异",
        "偏工作日驱动：周末聊得少",
        "强工作日驱动：周末基本沉默",
      ]);
      break;
    case "contact_diversity":
      scale = band(typeof d.H_norm_mean === "number" ? d.H_norm_mean : value, [[0.4], [0.7]], [
        "每周只跟固定的人说话",
        "每周接触面中等",
        "每周接触的人很杂",
      ]);
      break;
    case "topic_entropy":
      scale = band(typeof d.H_norm === "number" ? d.H_norm : value, [[0.4], [0.7]], [
        "反复聊少数几件事，注意力集中",
        "话题中等分散",
        "聊得很杂，话题分散",
      ]);
      break;
    case "attention_zipf":
      scale = band(value, [[0.8], [1.5]], [
        "秩-频斜率缓：注意力分散在很多对象上",
        "斜率中等：头部对象拿走较多注意力",
        "斜率陡：注意力高度集中在头部少数项",
      ]);
      break;
    case "ews_autocorr":
      scale = band(value, [[-0.2], [0.2]], [
        "自相关/方差在下降：状态弹性变好（弱信号）",
        "自相关/方差趋势平稳：没有临界慢化迹象",
        "自相关/方差在升高：状态变「黏」、恢复变慢，可能临近转折（弱证据，不得当诊断）",
      ]);
      break;
    case "dfa_alpha":
      scale = band(value, [[0.6], [1.2], [1.5]], [
        "≈白噪声：每天基本独立、无长程记忆",
        "有长程记忆：今天的状态会影响很久以后",
        "长程记忆很强",
        "非平稳：趋势主导，α 解读失效",
      ]);
      break;
    case "permutation_entropy":
      scale = band(value, [[0.5], [0.8]], [
        "起伏模式重复、可预测",
        "起伏模式中等可预测",
        "起伏模式杂乱、不可预测",
      ]);
      break;
    case "sample_entropy":
      scale = band(value, [[0.7], [1.5]], [
        "规律性高：序列重复",
        "规律性中等",
        "规律性低：序列复杂",
      ]);
      break;
    case "rqa":
      scale = band(value, [[0.2], [0.5]], [
        "DET 低：状态跳来跳去、不成串，模式不可预测",
        "DET 中等：偶尔成串延续",
        "DET 高：状态成串延续、模式可预测",
      ]);
      break;
    case "hmm_states":
      scale = value <= 3
        ? "状态数少：生活模式较单一"
        : value <= 5
          ? `在 ${value} 种生活模式间切换`
          : "状态数多：生活在多种模式间频繁切换";
      if (d.k_at_boundary) scale += "；k 落在搜索边界上，真状态数可能在范围外";
      break;
    case "cooccurrence_network":
      scale = band(value, [[0.3], [0.6]], [
        "模块度低：圈子互相连通，是一张网",
        "模块度中等：有部分互不相通的圈子",
        "模块度高：圈子之间互不相通",
      ]);
      break;
    case "multiplex_pagerank":
      scale = band(value, [[0.4], [0.8]], [
        "层间耦合弱：单聊/群聊里的重要人物各自为政",
        "层间耦合中等",
        "层间耦合强：跨场景都重要的人高度一致",
      ]);
      scale += "；注意该指标置换仅 15 次，p 分辨率≈0.063，读效应量别读 p";
      break;
    default:
      scale = "";
  }
  const ns = nullSentence(value, nb);
  if (!scale && !ns) return null;
  return `${scale ? `你的 ${f(value, 3)}：${scale}。` : ""}${ns}`;
}

/** 特质：把 (mean, sd, n) 翻成一句"偏哪边、多强、多一致" */
export function interpretTrait(mean: number | null, sd: number | null, n: number, promoted: boolean): string | null {
  if (mean == null || n < 1) return null;
  const dir = mean > 0.1 ? "偏正向" : mean < -0.1 ? "偏负向" : "接近中性（正负证据抵消）";
  const mag = Math.abs(mean) < 0.1 ? "倾向很弱" : Math.abs(mean) < 0.3 ? "中等倾向" : "较强倾向";
  const cons = sd == null ? "" : sd < 0.35 ? "，行为较一致" : sd < 0.6 ? "，行为有一定波动" : "，行为波动大（同一维度上表现不一）";
  return `${dir}·${mag}（mean ${mean >= 0 ? "+" : ""}${f(mean)}±${f(sd ?? 0)}，观测 ${n} 次）${cons}；` +
    (promoted ? "已跨 ≥3 独立会话，可作为稳定特质读。" : "独立会话不足 3，只当线索、别当结论。");
}

/** 成长代理分：分档 + 恒 0 的两维要明说"无信号" */
export function interpretGrowth(dim: string, score: number | null): string | null {
  if (score == null) return null;
  if (dim === "autonomy" || dim === "env_mastery") {
    return "聊天里没有可靠被动信号，恒 0 并标注——是「没测」，不是「你不行」。";
  }
  if (score <= 0.01) return "当前代理证据为 0：不是低，是没有可数的证据。";
  return band(score, [[0.34], [0.67]], ["代理分偏低", "代理分中等", "代理分较高"]) +
    "（行为代理，与构念距离远，别当量表分）。";
}

/** 情感剖面：四句分档 */
export function interpretAffect(a: {
  pa_mean: number | null; na_mean: number | null; inertia: number | null; granularity: number | null;
}): string {
  const pa = a.pa_mean ?? 0;
  const na = a.na_mean ?? 0;
  const bal = pa > na * 1.2 ? "正向占优" : na > pa * 1.2 ? "负向占优" : "正负大致持平";
  const iner = (a.inertia ?? 0) > 0.4 ? "情绪自我延续强（一旦进入某种情绪较难出来）"
    : (a.inertia ?? 0) > 0.15 ? "情绪惯性中等" : "情绪惯性低（切换快）";
  const gran = (a.granularity ?? 0) > 2.2 ? "情绪分辨细腻（标签丰富）"
    : (a.granularity ?? 0) > 1.2 ? "情绪分辨中等" : "情绪分辨粗（标签单一）";
  return `${bal}（正 ${f(pa)} / 负 ${f(na)}）；${iner}；${gran}。`;
}
