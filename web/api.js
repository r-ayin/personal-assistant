// api.js — 前端 ↔ personal-assistant 后端数据层。
// 同源托管（FastAPI 挂 /web）时 BASE="" 走相对路径，免 CORS；另行托管时设 window.PA_BASE="http://host:port"。
// bootstrap() 启动时把列表端点灌进 window.MockData（形状对齐者直接覆盖；失败/为空回落原 mock）。
// 写操作走 PA.post 后 updateMock() 触发 pa-update 事件，App 监听后强制重渲染。
(function () {
  const BASE = window.PA_BASE || "";
  const LIVE = { ok: false, sources: {} };

  async function get(path, params) {
    try {
      const qs = params ? "?" + new URLSearchParams(params).toString() : "";
      const r = await fetch(BASE + path + qs, { headers: { "Accept": "application/json" } });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }
  async function post(path, body) {
    try {
      const r = await fetch(BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(body || {})
      });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  function updateMock(field, value) {
    if (window.MockData && field) window.MockData[field] = value;
    window.dispatchEvent(new CustomEvent("pa-update"));
  }
  function setLive(field, ok) { LIVE.sources[field] = !!ok; if (ok) LIVE.ok = true; }

  // persona 后端→前端映射。⚠ 后端 /profile 不产 score，此处 score 为占位（0.6 有内容/0.2 空），
  // 非真实评估值；summary 取后端维度原文；evidence 后端不返回→空。
  function mapPersona(p) {
    if (!p || !p.profile) return null;
    const pf = p.profile;
    const mapping = [
      ["identity", pf.personality],
      ["values", pf.values],
      ["cognition", pf.thinking_patterns],
      ["preferences", pf.preferences],
      ["goals", pf.goals],
      ["emotionalStyle", pf.affective_baseline],
      ["knowledgeAreas", pf.knowledge],
    ];
    const profile = {};
    for (const [k, txt] of mapping) {
      profile[k] = { score: txt ? 0.6 : 0.2, summary: txt || "（暂无）", evidence: [] };
    }
    return { version: p.version || 0, change_summary: p.change_summary || "", profile };
  }

  // verify 后端→前端映射。后端 run_all() 返回 kept/deleted 计数（无 item 明细），assertion=passed/failed。
  function mapVerify(v) {
    if (!v) return null;
    const kept = (v.events_kept || 0) + (v.reminders_kept || 0) + (v.memories_kept || 0);
    const deleted = (v.events_deleted || 0) + (v.reminders_deleted || 0) + (v.memories_deleted || 0);
    const total = kept + deleted;
    return {
      status: deleted > 0 ? "partial" : "passed",
      passed: kept, failed: deleted, warned: 0, total: total || 0,
      items: v.items || [],   // 后端无 item 明细 → 空，VerifyPage 显示计数不显示明细行
    };
  }

  async function bootstrap() {
    const m = window.MockData;
    const lists = [
      ["segments", "/segments", j => j && j.segments ? j.segments : null],
      ["memories", "/memories", j => j && j.memories ? j.memories : null],
      ["events", "/events", j => j && j.events ? j.events : null],
      ["reminders", "/reminders", j => j && j.reminders ? j.reminders : null],
      ["chatLog", "/chat-log", j => j && j.logs ? j.logs : null],
      ["speakers", "/speakers", j => j && j.speakers ? j.speakers : null],
      ["wikiPages", "/wiki", j => j && j.pages ? j.pages : null],
    ];
    await Promise.all(lists.map(async ([field, path, pick]) => {
      const j = await get(path);
      const val = pick(j);
      setLive(field, !!val);
      if (val && val.length) m[field] = val;   // 空数组不覆盖（保留 mock 示例）
    }));
    // health（后端只回 backend 名，inbox/db/latency 保留 mock）
    const h = await get("/health");
    if (h) {
      m.health = Object.assign({}, m.health, { api: "running", llm: h.llm, asr: h.asr, embedder: h.embedder, speaker: h.speaker });
      setLive("health", true);
    }
    // persona（部分映射；versions 历史保留 mock）
    const pr = await get("/profile");
    const pm = mapPersona(pr);
    setLive("persona", !!pm);
    if (pm) { pm.versions = (m.persona && m.persona.versions) || []; m.persona = Object.assign({}, m.persona, pm); }
    // verify
    const vr = await post("/verify", {});
    const vm = mapVerify(vr);
    setLive("verify", !!vm);
    if (vm) m.verifyReport = Object.assign({}, m.verifyReport, vm);
    // recommendations（按 kind 各取一次）
    const recs = {};
    let anyRec = false;
    for (const k of ["book", "movie", "action"]) {
      const j = await get("/recommend", { kind: k });
      if (j && j.recommendations && j.recommendations.length) {
        recs[k] = j.recommendations.map(r => ({
          item: r.item, reason: r.reason,
          based_on: r.based_on ? [r.based_on] : [],
          from_search: k !== "action"
        }));
        anyRec = true;
      }
    }
    setLive("recommendations", anyRec);
    if (anyRec) m.recommendations = Object.assign({}, m.recommendations, recs);
    window.dispatchEvent(new CustomEvent("pa-update"));
    return LIVE;
  }

  window.PA = { BASE, get, post, bootstrap, updateMock, mapVerify, mapPersona, live: LIVE };
})();
