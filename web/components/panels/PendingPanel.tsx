"use client";

import Reveal from "@/components/Reveal";

/**
 * 后端尚未产出数据时的诚实占位面板。
 *
 * 铁律：**绝不编造假数据、假图表、假指标**。这里只说明这块面板在等哪一个后端阶段、
 * 具体等哪几件产物；等接通了就换回真实面板。宁可空着，也不给一个看起来像真的的数。
 */
export default function PendingPanel({
  title,
  waiting,
  needs,
}: {
  title: string;
  /** 在等什么：后端阶段 + 未产出的东西 */
  waiting: string;
  /** 具体依赖项：脚本 / 接口 / 算法 */
  needs?: string[];
}) {
  return (
    <Reveal as="section" className="glass-card p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2
          className="text-xl font-semibold"
          style={{ fontFamily: "var(--font-serif)", color: "var(--text-main)" }}
        >
          {title}
        </h2>
        <span
          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium"
          style={{ background: "var(--och-08)", color: "var(--caution)" }}
        >
          等待后端
        </span>
      </div>

      <p
        className="mt-4 text-sm"
        style={{ color: "var(--text-dim)", lineHeight: 1.9 }}
      >
        这块面板暂时没有内容可展示——{waiting}。
      </p>

      {needs && needs.length > 0 && (
        <div
          className="mt-6 pt-5"
          style={{ borderTop: "1px solid var(--edge)" }}
        >
          <div
            className="text-xs mb-3"
            style={{
              color: "var(--text-weak)",
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.06em",
            }}
          >
            接通它需要
          </div>
          <ul className="flex flex-col gap-2.5">
            {needs.map((n) => (
              <li
                key={n}
                className="flex items-start gap-3 text-[13px]"
                style={{ color: "var(--text-dim)", lineHeight: 1.8 }}
              >
                <span
                  aria-hidden
                  className="mt-[9px] inline-block shrink-0"
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: 1,
                    background: "var(--caution)",
                    transform: "rotate(45deg)",
                  }}
                />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{n}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p
        className="serif mt-6 text-[13px]"
        style={{ color: "var(--text-weak)", letterSpacing: "0.04em" }}
      >
        在数据真正长出来之前，这里不放任何示例数字。
      </p>
    </Reveal>
  );
}
