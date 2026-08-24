import { Bot, Eye, Radio, Server } from "lucide-react";

export type ServiceState = "online" | "offline" | "idle" | "error" | "loading";

export interface StatusStripProps {
  pa: ServiceState;
  model: ServiceState;
  perception: ServiceState;
  overlay: ServiceState;
}

const LABELS: Record<ServiceState, string> = {
  online: "在线",
  offline: "离线",
  idle: "待机",
  error: "异常",
  loading: "检查中",
};

export default function StatusStrip({ pa, model, perception, overlay }: StatusStripProps) {
  const items = [
    { key: "pa", label: "PA", state: pa, icon: Server },
    { key: "model", label: "模型", state: model, icon: Bot },
    { key: "perception", label: "感知", state: perception, icon: Eye },
    { key: "overlay", label: "浮层", state: overlay, icon: Radio },
  ];

  return (
    <section className="status-strip" aria-label="运行状态">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div className="status-item" key={item.key} data-testid={`status-${item.key}`}>
            <Icon size={14} aria-hidden="true" />
            <span>{item.label}</span>
            <span className={`status-dot status-${item.state}`} aria-hidden="true" />
            <strong>{LABELS[item.state]}</strong>
          </div>
        );
      })}
    </section>
  );
}
