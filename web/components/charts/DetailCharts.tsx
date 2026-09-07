"use client";

import {
  Bar, BarChart, Cell, ComposedChart, Line, LineChart, ReferenceLine,
  ResponsiveContainer, XAxis, YAxis,
} from "recharts";
import NullBandChart from "./NullBandChart";
import { axisProps, fmtTick, useChartTheme } from "./theme";
import { useChartMotion } from "./useChartMotion";

/** 明细图统一外壳：浅墨底 + 标题 + 一句"怎么读" */
function ChartBlock({ title, note, height, children }: {
  title: string; note?: string; height?: number; children: React.ReactNode;
}) {
  return (
    <div className="mt-2 rounded-md bg-[var(--ink-02)] p-3">
      <p className="mb-1 text-[11px] font-medium text-[var(--ink-700)]">{title}</p>
      <div style={{ height }} className="w-full">{children}</div>
      {note && <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--text-weak)]">{note}</p>}
    </div>
  );
}

const arr = (v: unknown): number[] | null =>
  Array.isArray(v) && v.length && v.every((x) => typeof x === "number" && Number.isFinite(x))
    ? (v as number[]) : null;
const strs = (v: unknown): string[] | null =>
  Array.isArray(v) && v.length && v.every((x) => typeof x === "string") ? (v as string[]) : null;

/** 人名/会话名截断：p:xxx / conv:xxx 前缀去掉，超 8 字省略 */
function shortName(s: string): string {
  const bare = s.replace(/^(p|conv|g):/, "");
  return bare.length > 8 ? `${bare.slice(0, 8)}…` : bare;
}

/* ── 社交签名：top20 份额柱 ─────────────────────────────────────── */
export function SignatureSharesChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const shares = arr(detail.shares_top20);
  const units = strs(detail.top_units);
  if (!shares || !units) return null;
  const data = shares.map((s, i) => ({ name: shortName(units[i] ?? `#${i + 1}`), share: s }));
  return (
    <ChartBlock
      title="注意力份额 · top20（柱高=该人/会话占你全部消息的份额）"
      note="曲线陡=注意力集中在头部少数对象；第一根朱砂柱即 headline 的 top1 份额。"
      height={168}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
          <XAxis dataKey="name" {...axisProps(t)} interval={1} tickFormatter={shortName} />
          <YAxis {...axisProps(t)} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
          <Bar dataKey="share" isAnimationActive={anim} animationDuration={dur} radius={[2, 2, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? t.accent : t.ink18} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 邓巴分层：每圈人数柱 + 份额标注 ────────────────────────────── */
export function DunbarLayersChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const sizes = arr(detail.layer_sizes);
  const mass = arr(detail.layer_mass);
  if (!sizes) return null;
  const data = sizes.map((n, i) => ({
    layer: `第${i + 1}圈`, people: n, mass: mass?.[i],
  }));
  const bps = arr(detail.breakpoints_rank);
  return (
    <ChartBlock
      title={`亲疏圈层 · ${sizes.length} 层（柱高=该圈人数）`}
      note={
        "断点由 PELT 变点检测在秩-份额曲线上自动检出" +
        (bps ? `（秩 ${bps.map((b) => b + 1).join(" / ")} 处）` : "") +
        "，不是硬套 5/15/50/150；1 层=检不出断点，不等于没有圈层。" +
        (mass ? `各圈消息份额：${mass.map((m, i) => `第${i + 1}圈 ${(m * 100).toFixed(1)}%`).join("、")}。` : "")
      }
      height={150}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 0, left: -22 }}>
          <XAxis dataKey="layer" {...axisProps(t)} />
          <YAxis {...axisProps(t)} allowDecimals={false} />
          <Bar
            dataKey="people" isAnimationActive={anim} animationDuration={dur}
            radius={[2, 2, 0, 0]}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? t.accent : i === 1 ? t.interactive : t.ink18} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 社交熵分解：单层份额堆叠 + 层内熵 ──────────────────────────── */
export function EntropyLayersChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const mass = arr(detail.layer_mass);
  const layerH = arr(detail.layer_H);
  if (!mass) return null;
  const row: Record<string, number | string> = { name: "份额" };
  mass.forEach((m, i) => { row[`L${i + 1}`] = m; });
  const fills = [t.accent, t.interactive, t.positive, t.caution, t.ink18, t.ink300];
  return (
    <ChartBlock
      title="消息份额在圈层间的分配（整条=100%）"
      note={
        `总熵 ${fmt(detail.H_global)} = 层内 ${fmt(detail.H_within)} + 层间 ${fmt(detail.H_between)}（nat）；` +
        (layerH ? `各层内部熵：${layerH.map((h, i) => `第${i + 1}圈 ${h.toFixed(2)}`).join("、")}。` : "") +
        "层间占比高=注意力在圈层之间分配得均匀。"
      }
      height={54}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <ComposedChart layout="vertical" data={[row]} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <XAxis type="number" domain={[0, 1]} hide />
          <YAxis type="category" dataKey="name" hide />
          {mass.map((_, i) => (
            <Bar
              key={i} dataKey={`L${i + 1}`} stackId="m" fill={fills[i % fills.length]}
              isAnimationActive={anim} animationDuration={dur}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

function fmt(v: unknown): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(2) : "—";
}

/* ── 24 小时作息环展开成柱 ─────────────────────────────────────── */
export function CircadianChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const hours = arr(detail.hour_profile);
  if (!hours || hours.length !== 24) return null;
  const data = hours.map((c, h) => ({ h: `${h}时`, count: c }));
  const peak = typeof detail.peak_hour === "number" ? detail.peak_hour : null;
  const chrono = typeof detail.chronotype_hour === "number" ? detail.chronotype_hour : null;
  return (
    <ChartBlock
      title="24 小时消息分布（柱高=该小时消息数）"
      note={
        `强度 ${fmt(detail.strength)} = 1 − 小时分布熵/ln24；` +
        (peak != null ? `峰值 ${peak} 时` : "") +
        (chrono != null ? `，圆形均值作息点 ${chrono.toFixed(1)} 时（朱砂线）` : "") +
        "。接近 1=固定时段活跃，接近 0=昼夜不分。"
      }
      height={132}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -22 }}>
          <XAxis dataKey="h" {...axisProps(t)} interval={3} />
          <YAxis {...axisProps(t)} />
          {chrono != null && (
            <ReferenceLine x={`${Math.round(chrono)}时`} stroke={t.accent} strokeWidth={1.5} />
          )}
          <Bar dataKey="count" fill={t.interactive} isAnimationActive={anim} animationDuration={dur}
            radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 星期节律：7 柱 + 工作日/周末均值线 ─────────────────────────── */
const DOW = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
export function WeeklyRhythmChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const dow = arr(detail.dow_profile);
  if (!dow || dow.length !== 7) return null;
  const data = dow.map((c, i) => ({ d: DOW[i], count: c }));
  const wd = typeof detail.workday_mean === "number" ? detail.workday_mean : null;
  const we = typeof detail.weekend_mean === "number" ? detail.weekend_mean : null;
  return (
    <ChartBlock
      title="星期分布（柱高=该星期几的消息数；靛青=工作日，赭石=周末）"
      note={
        `headline 比值 ${fmt(detail.workday_weekend_ratio)} = 工作日日均 ${fmt(wd)} ÷ 周末日均 ${fmt(we)}；` +
        `虚线为两条均值。>1 工作日驱动，<1 周末驱动，≈1 无差异。`
      }
      height={140}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
          <XAxis dataKey="d" {...axisProps(t)} />
          <YAxis {...axisProps(t)} />
          {wd != null && <ReferenceLine y={wd} stroke={t.interactive} strokeDasharray="4 4" />}
          {we != null && <ReferenceLine y={we} stroke={t.caution} strokeDasharray="4 4" />}
          <Bar dataKey="count" isAnimationActive={anim} animationDuration={dur} radius={[2, 2, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={i >= 5 ? t.caution : t.interactive} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 话题高频词 top12 ──────────────────────────────────────────── */
export function TopicTokensChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const toks = Array.isArray(detail.top_tokens) ? detail.top_tokens : null;
  if (!toks || !toks.length) return null;
  const data = toks.slice(0, 12).map((p: any) => ({
    word: Array.isArray(p) ? String(p[0]) : String(p?.word ?? ""),
    count: Array.isArray(p) ? Number(p[1]) : Number(p?.count ?? 0),
  })).filter((d: any) => d.word && Number.isFinite(d.count));
  if (!data.length) return null;
  return (
    <ChartBlock
      title="高频话题词 top12（条长=出现次数，二元词组）"
      note={`话题熵 ${fmt(detail.H)}（归一 ${fmt(detail.H_norm)}）：越高=聊得越杂；` +
        `词表 ${fmt(detail.V_distinct_bigrams)} 个二元词、抽样 ${fmt(detail.n_tokens_all)} 词元。是词频代理，不是主题模型。`}
      height={data.length * 22 + 16}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <ComposedChart layout="vertical" data={data} margin={{ top: 0, right: 24, bottom: 0, left: 8 }}>
          <XAxis type="number" {...axisProps(t)} allowDecimals={false} />
          <YAxis type="category" dataKey="word" width={76} {...axisProps(t)}
            tick={{ fill: t.ink500, fontSize: 11 }} />
          <Bar dataKey="count" fill={t.ink18} isAnimationActive={anim} animationDuration={dur}
            radius={[0, 2, 2, 0]}>
            {data.map((_: any, i: number) => (
              <Cell key={i} fill={i === 0 ? t.accent : t.ink18} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── DFA log-log 曲线 ──────────────────────────────────────────── */
export function DfaCurveChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const scales = arr(detail.scales);
  const F = arr(detail.F);
  if (!scales || !F || scales.length !== F.length || scales.length < 3) return null;
  const data = scales.map((s, i) => ({ s, F: F[i] }));
  return (
    <ChartBlock
      title="去趋势波动分析：尺度 n 与涨落 F(n) 的双对数曲线"
      note={`斜率 α=${fmt(detail.alpha)}（R²=${fmt(detail.r2)}）：≈0.5 白噪声无记忆，≈1 粉红噪声有长程记忆，>1.5 非平稳。点为实测，线为眼视引导，未画拟合外推。`}
      height={150}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
          <XAxis dataKey="s" type="number" scale="log" domain={["dataMin", "dataMax"]} {...axisProps(t)} tickFormatter={fmtTick} />
          <YAxis scale="log" domain={["dataMin", "dataMax"]} {...axisProps(t)} tickFormatter={fmtTick} />
          <Line type="linear" dataKey="F" stroke={t.interactive} strokeWidth={1.5}
            dot={{ r: 2.5, fill: t.accent, strokeWidth: 0 }}
            isAnimationActive={anim} animationDuration={dur} />
        </LineChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── RQA 四子量森林图 ──────────────────────────────────────────── */
const RQA_KEYS: [string, string][] = [
  ["RR", "递归率 RR"], ["DET", "决定论度 DET"], ["ENTR", "对角线熵 ENTR"], ["Lmax", "最长对角线 Lmax"],
];
export function RqaForest({ detail }: { detail: Record<string, any> }) {
  const ci = (detail.ci_by_measure ?? {}) as Record<string, [number, number]>;
  const nm = (detail.null_mean_by_measure ?? {}) as Record<string, number>;
  if (!detail || typeof detail.DET !== "number") return null;
  return (
    <div className="mt-2 space-y-1 rounded-md bg-[var(--ink-02)] p-3">
      <p className="text-[11px] font-medium text-[var(--ink-700)]">
        递归定量分析四子量 · 各自对比随机基线（灰带）
      </p>
      {RQA_KEYS.map(([k, zh]) => (
        <div key={k}>
          <p className="font-mono text-[10.5px] text-[var(--text-dim)]">
            {zh}　观测 {fmt(detail[k])}
          </p>
          <NullBandChart
            observed={typeof detail[k] === "number" ? detail[k] : null}
            ciLow={ci[k]?.[0]} ciHigh={ci[k]?.[1]} nullMean={nm[k]}
            q025={undefined} q975={undefined} height={54}
          />
        </div>
      ))}
      <p className="text-[10.5px] leading-relaxed text-[var(--text-weak)]">
        RR 高=常回到相似状态；DET 高=状态成串延续、模式可预测；ENTR 高=延续时长多样、模式复杂；Lmax 大=稳定期长、抗扰动。
      </p>
    </div>
  );
}

/* ── HMM：状态条 + 转移矩阵 + BIC ──────────────────────────────── */
export function HmmCharts({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const path = arr(detail.viterbi_path_tail);
  const matrix = Array.isArray(detail.transition_matrix) ? detail.transition_matrix : null;
  const bic = detail.bic_by_k as Record<string, number> | undefined;
  if (!path && !matrix && !bic) return null;
  const palette = [t.ink06, t.ink300, t.caution, t.interactive, t.positive];
  const STEPS = [t.ink02, t.ink06, t.ink12, t.ink18, t.ink300, t.ink500, t.ink700, t.ink900];
  const bicData = bic
    ? Object.entries(bic).map(([k, v]) => ({ k: `k=${k}`, v }))
    : [];
  const minBic = bicData.length ? Math.min(...bicData.map((d) => d.v)) : null;
  return (
    <div className="mt-2 space-y-3 rounded-md bg-[var(--ink-02)] p-3">
      {!!path?.length && (
        <div>
          <p className="mb-1 text-[11px] font-medium text-[var(--ink-700)]">
            最近 {path.length} 天的隐状态序列（Viterbi 解码尾段，一格=一天）
          </p>
          <div className="flex gap-[2px]">
            {path.map((s, i) => (
              <span
                key={i}
                title={`第 ${i + 1} 天 → 状态 ${s}`}
                className="h-5 flex-1 rounded-[2px]"
                style={{ background: palette[((s % palette.length) + palette.length) % palette.length] }}
              />
            ))}
          </div>
          <p className="mt-1 text-[10.5px] text-[var(--text-weak)]">
            颜色=状态编号；连续同色=一段稳定期。切换率 {fmt(detail.switch_rate)} / 天。
          </p>
        </div>
      )}
      {matrix && (
        <div>
          <p className="mb-1 text-[11px] font-medium text-[var(--ink-700)]">
            状态转移矩阵（行=今天，列=明天；越深=转移概率越大）
          </p>
          <div className="grid gap-[2px]" style={{ gridTemplateColumns: `repeat(${matrix.length}, minmax(0,1fr))` }}>
            {matrix.map((row: number[], i: number) =>
              row.map((v: number, j: number) => {
                const bucket = Math.max(0, Math.min(STEPS.length - 1, Math.floor(v * STEPS.length)));
                return (
                  <span
                    key={`${i}-${j}`}
                    title={`状态${i} → 状态${j}：${(v * 100).toFixed(1)}%`}
                    className="flex h-7 items-center justify-center rounded-[2px] font-mono text-[9.5px]"
                    style={{ background: STEPS[bucket], color: bucket >= 4 ? t.surface : t.ink700 }}
                  >
                    {v >= 0.05 ? `${Math.round(v * 100)}` : ""}
                  </span>
                );
              }),
            )}
          </div>
        </div>
      )}
      {bicData.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium text-[var(--ink-700)]">
            状态数选择：BIC 越低越好（朱砂点=被选中的 k）
          </p>
          <div style={{ height: 120 }} className="w-full">
            <ResponsiveContainer width="100%" height="100%" debounce={80}>
              <LineChart data={bicData} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
                <XAxis dataKey="k" {...axisProps(t)} />
                <YAxis {...axisProps(t)} tickFormatter={fmtTick} />
                <Line type="monotone" dataKey="v" stroke={t.interactive} strokeWidth={1.5}
                  isAnimationActive={anim} animationDuration={dur}
                  dot={(p: any) => (
                    <circle key={p.payload.k} cx={p.cx} cy={p.cy} r={p.payload.v === minBic ? 5 : 2.5}
                      fill={p.payload.v === minBic ? t.accent : t.interactive} />
                  )}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── 共现网络：社群规模柱 ──────────────────────────────────────── */
export function CommunitySizesChart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const sizes = arr(detail.community_sizes);
  if (!sizes) return null;
  const data = sizes.map((n, i) => ({ c: `#${i + 1}`, n }));
  const bal = detail.balance as Record<string, any> | undefined;
  return (
    <ChartBlock
      title={`Louvain 社群规模（${sizes.length} 个圈子，柱高=人数）`}
      note={
        `模块度 Q=${fmt(detail.modularity_Q_unweighted)}、聚类 ${fmt(detail.avg_clustering)}；` +
        (bal
          ? `结构平衡（Heider）：带符号三角中平衡占 ${(Number(bal.balanced_frac) * 100).toFixed(1)}%，` +
            `对比符号随机基线 ${(Number(bal.null_mean) * 100).toFixed(1)}%，p=${Number(bal.p_value).toFixed(3)}。`
          : "") +
        "圈子大小悬殊=社交圈分层明显。"
      }
      height={140}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <XAxis dataKey="c" {...axisProps(t)} interval={1} />
          <YAxis {...axisProps(t)} allowDecimals={false} />
          <Bar dataKey="n" fill={t.ink18} isAnimationActive={anim} animationDuration={dur} radius={[2, 2, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? t.accent : t.ink18} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 多层重要度 top10 堆叠 ─────────────────────────────────────── */
export function MultiplexTop10Chart({ detail }: { detail: Record<string, any> }) {
  const t = useChartTheme();
  const { anim, dur } = useChartMotion();
  const top = Array.isArray(detail.top10_multiplex) ? detail.top10_multiplex : null;
  if (!top || !top.length) return null;
  const layers = [...new Set(top.flatMap((r: any) => Object.keys(r?.per_layer ?? {})))];
  if (!layers.length) return null;
  const data = top.map((r: any) => ({ node: shortName(String(r.node)), ...r.per_layer }));
  const fills: Record<string, string> = {
    text: t.interactive, group: t.positive, audio: t.caution,
  };
  return (
    <ChartBlock
      title="跨层重要度 top10（条长=聚合 PageRank，分段=各层贡献）"
      note={`层：${layers.join(" / ")}（靛青=单聊文字，石绿=群聊，赭石=语音）；` +
        `headline ${fmt(detail.spearman_coupled_vs_decoupled)} 是"耦合 vs 解耦排序"的 Spearman ρ，量的是层间耦合敏感度，不是某个人的分数。`}
      height={data.length * 22 + 16}
    >
      <ResponsiveContainer width="100%" height="100%" debounce={80}>
        <ComposedChart layout="vertical" data={data} margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
          <XAxis type="number" {...axisProps(t)} />
          <YAxis type="category" dataKey="node" width={80} {...axisProps(t)}
            tick={{ fill: t.ink500, fontSize: 11 }} />
          {layers.map((L) => (
            <Bar key={L} dataKey={L} stackId="p" fill={fills[L] ?? t.ink18}
              isAnimationActive={anim} animationDuration={dur} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartBlock>
  );
}

/* ── 分派器 ───────────────────────────────────────────────────── */
export default function MetricDetailChart({ name, detail }: {
  name: string;
  detail: Record<string, any>;
}) {
  if (!detail || typeof detail !== "object") return null;
  switch (name) {
    case "signature_shares": return <SignatureSharesChart detail={detail} />;
    case "dunbar_layers": return <DunbarLayersChart detail={detail} />;
    case "social_entropy": return <EntropyLayersChart detail={detail} />;
    case "circadian_strength": return <CircadianChart detail={detail} />;
    case "weekly_rhythm": return <WeeklyRhythmChart detail={detail} />;
    case "topic_entropy": return <TopicTokensChart detail={detail} />;
    case "dfa_alpha": return <DfaCurveChart detail={detail} />;
    case "rqa": return <RqaForest detail={detail} />;
    case "hmm_states": return <HmmCharts detail={detail} />;
    case "cooccurrence_network": return <CommunitySizesChart detail={detail} />;
    case "multiplex_pagerank": return <MultiplexTop10Chart detail={detail} />;
    default: return null;
  }
}
