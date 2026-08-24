"use client";

import { useEffect, useMemo, useState } from "react";
import ConversationPanel from "@/components/ConversationPanel";
import StatusStrip, { type ServiceState } from "@/components/StatusStrip";
import TodayRail from "@/components/TodayRail";
import { api } from "@/lib/api";
import { liveClient, type LiveState } from "@/lib/live";
import type { ChatLog, Event, LiveEvent, Reminder, RuntimeStatus } from "@/lib/types";

interface TodayData {
  messages: ChatLog[];
  events: Event[];
  reminders: Reminder[];
  model: RuntimeStatus | null;
  overlayClients: number;
  overlayEnabled: boolean;
}

const EMPTY_DATA: TodayData = {
  messages: [],
  events: [],
  reminders: [],
  model: null,
  overlayClients: 0,
  overlayEnabled: false,
};

function modelState(status: RuntimeStatus | null): ServiceState {
  if (!status) return "loading";
  if (status.error || status.state === "failed") return "error";
  if (status.running || status.state === "ready") return "online";
  return "idle";
}

export default function TodayPage() {
  const [data, setData] = useState<TodayData>(EMPTY_DATA);
  const [liveState, setLiveState] = useState<LiveState>(liveClient.getState());
  const [liveEvent, setLiveEvent] = useState<LiveEvent | null>(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      api.chatLog("50"),
      api.events(),
      api.reminders(),
      api.localModelStatus(),
      api.barrageStatus(),
      api.health(),
    ])
      .then(([chat, events, reminders, model, barrage]) => {
        if (!active) return;
        setData({
          messages: [...chat.chat_log].reverse(),
          events: events.events,
          reminders: reminders.reminders,
          model,
          overlayClients: barrage.overlay_clients,
          overlayEnabled: barrage.settings.enabled && !barrage.paused,
        });
      })
      .catch((error: unknown) => {
        if (active) setLoadError(error instanceof Error ? error.message : "今日信息加载失败");
      });

    const unsubscribeState = liveClient.subscribeState(setLiveState);
    const unsubscribeEvent = liveClient.subscribe((event) => {
      setLiveEvent(event);
      if (event.type === "reminder") {
        const item = event.data as Partial<Reminder>;
        if (item.id && item.what) {
          setData((current) => ({
            ...current,
            reminders: [{
              id: item.id || "",
              what: item.what || "",
              when_dt: item.when_dt || event.ts,
              when_raw: item.when_raw || "刚刚",
              recurring: item.recurring || "",
              source_segment: item.source_segment || "",
              fired: item.fired || 0,
              created_at: item.created_at || event.ts,
            }, ...current.reminders.filter((existing) => existing.id !== item.id)],
          }));
        }
      } else if (event.type === "local_model_status") {
        setData((current) => ({ ...current, model: event.data as unknown as RuntimeStatus }));
      }
    });
    liveClient.connect();

    return () => {
      active = false;
      unsubscribeState();
      unsubscribeEvent();
      liveClient.disconnect();
    };
  }, []);

  const statuses = useMemo(() => {
    const perceptionOnline = data.model?.consumers.includes("perception") || false;
    return {
      pa: (liveState.connected ? "online" : liveState.lastError ? "offline" : "loading") as ServiceState,
      model: modelState(data.model),
      perception: (perceptionOnline ? "online" : "idle") as ServiceState,
      overlay: (data.overlayEnabled && data.overlayClients > 0 ? "online" : data.overlayEnabled ? "idle" : "offline") as ServiceState,
    };
  }, [data, liveState]);

  return (
    <div className="today-page">
      <StatusStrip {...statuses} />
      {loadError && <div className="today-error" role="alert">{loadError}</div>}
      <div className="today-workspace">
        <ConversationPanel
          initialMessages={data.messages}
          connected={liveState.connected}
          liveEvent={liveEvent}
        />
        <TodayRail reminders={data.reminders} events={data.events} />
      </div>
    </div>
  );
}
