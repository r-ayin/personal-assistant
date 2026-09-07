/**
 * 图表异步 chunk 的加载占位。
 * 可见性铁律：占位必须是"看得见的静态内容"，不是 opacity:0 的空洞——
 * 固定高度防布局跳动，一行弱文字说明在等什么。
 */
export default function ChartSkeleton({ height = 160, label = "图表加载中…" }: {
  height?: number;
  label?: string;
}) {
  return (
    <div
      className="flex items-end justify-center rounded-md bg-[var(--ink-02)]"
      style={{ height }}
      role="status"
      aria-label={label}
    >
      <span className="pb-3 font-mono text-[11px] text-[var(--text-weak)]">{label}</span>
    </div>
  );
}
