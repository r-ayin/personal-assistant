import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConversationPanel from "./ConversationPanel";
import StatusStrip from "./StatusStrip";
import { api } from "@/lib/api";
import type { LiveEvent } from "@/lib/types";

afterEach(() => vi.restoreAllMocks());

describe("Today workspace", () => {
  it("shows PA, model, perception and overlay as independent statuses", () => {
    render(<StatusStrip pa="online" model="error" perception="idle" overlay="offline" />);

    expect(within(screen.getByTestId("status-pa")).getByText("在线")).toBeInTheDocument();
    expect(within(screen.getByTestId("status-model")).getByText("异常")).toBeInTheDocument();
    expect(within(screen.getByTestId("status-perception")).getByText("待机")).toBeInTheDocument();
    expect(within(screen.getByTestId("status-overlay")).getByText("离线")).toBeInTheDocument();
  });

  it("calls chat once and renders reply evidence", async () => {
    const chat = vi.spyOn(api, "chat").mockResolvedValue({ reply: "先完成评审。", evidence: ["memory:review"] });
    render(<ConversationPanel initialMessages={[]} connected liveEvent={null} />);

    fireEvent.change(screen.getByLabelText("消息"), { target: { value: "现在先做什么？" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("先完成评审。");
    expect(chat).toHaveBeenCalledOnce();
    expect(chat).toHaveBeenCalledWith("现在先做什么？");
    expect(screen.getByText("memory:review")).toBeInTheDocument();
  });

  it("回传服务端提供的 conversation id", async () => {
    const chat = vi.spyOn(api, "chat")
      .mockResolvedValueOnce({ reply: "第一条回复", evidence: [], conversation_id: "conversation-1" })
      .mockResolvedValueOnce({ reply: "第二条回复", evidence: [], conversation_id: "conversation-1" });
    render(<ConversationPanel initialMessages={[]} connected liveEvent={null} />);

    const input = screen.getByLabelText("消息");
    fireEvent.change(input, { target: { value: "第一条消息" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await screen.findByText("第一条回复");

    fireEvent.change(input, { target: { value: "第二条消息" } });
    fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await screen.findByText("第二条回复");

    expect(chat.mock.calls).toEqual([
      ["第一条消息"],
      ["第二条消息", "conversation-1"],
    ]);
  });

  it("renders chat_reply while ignoring barrage content", () => {
    const { rerender } = render(<ConversationPanel initialMessages={[]} connected liveEvent={null} />);
    const barrage: LiveEvent = { type: "barrage", data: { text: "不应出现的浮层消息" }, ts: "2026-07-31T09:00:00Z" };
    rerender(<ConversationPanel initialMessages={[]} connected liveEvent={barrage} />);
    expect(screen.queryByText("不应出现的浮层消息")).not.toBeInTheDocument();

    const reply: LiveEvent = {
      type: "chat_reply",
      data: { text: "实时回复", evidence: ["memory:live"], is_partial: false },
      ts: "2026-07-31T09:00:01Z",
    };
    rerender(<ConversationPanel initialMessages={[]} connected liveEvent={reply} />);
    expect(screen.getByText("实时回复")).toBeInTheDocument();
    expect(screen.getByText("memory:live")).toBeInTheDocument();
  });

  it("disables send when disconnected and preserves the draft", async () => {
    const chat = vi.spyOn(api, "chat").mockResolvedValue({ reply: "不会调用", evidence: [] });
    render(<ConversationPanel initialMessages={[]} connected={false} liveEvent={null} />);

    const input = screen.getByLabelText("消息");
    fireEvent.change(input, { target: { value: "连接恢复后发送" } });
    const send = screen.getByRole("button", { name: "发送消息" });

    expect(send).toBeDisabled();
    fireEvent.click(send);
    await waitFor(() => expect(chat).not.toHaveBeenCalled());
    expect(input).toHaveValue("连接恢复后发送");
  });
});
