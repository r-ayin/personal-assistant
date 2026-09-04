import "@testing-library/jest-dom/vitest";

// Node 24 内置 localStorage 未配置 --localstorage-file 时全局存在但不可用，
// 且会遮蔽 jsdom 的实现；这里补一个内存实现保证测试可跑。
if (typeof globalThis.localStorage === "undefined" || !globalThis.localStorage?.getItem) {
  const store = new Map<string, string>();
  const mock: Storage = {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => [...store.keys()][i] ?? null,
    removeItem: (k: string) => { store.delete(k); },
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
  };
  Object.defineProperty(globalThis, "localStorage", { value: mock, configurable: true, writable: true });
}

// jsdom 不实现滚动。ChatPanel 的消息流容器用 el.scrollTo(...) 贴底，
// KnowledgePanel 选中卡片后用 window.scrollTo(...) 回顶；补 no-op 垫片，
// 否则组件一挂载就抛 TypeError。仅在缺失时补，不覆盖真实实现。
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {};
}
if (typeof window !== "undefined" && typeof window.scrollTo !== "function") {
  window.scrollTo = (() => {}) as unknown as typeof window.scrollTo;
}
