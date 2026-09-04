"use client";

export default function EmptyState({ message = "这里还在沉睡，等待第一颗种子发芽" }: { message?: string }) {
  return (
    <div className="empty-seed">
      <div className="empty-seed-dot" />
      <p className="empty-seed-text">{message}</p>
    </div>
  );
}
