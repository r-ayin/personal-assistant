// api.js — 前端 ↔ personal-assistant 后端数据层（全覆盖版）
// 同源托管（FastAPI 挂 /web）时 BASE="" 走相对路径，免 CORS
// bootstrap() 启动时灌数据进 window.MockData
(function () {
  const BASE = window.PA_BASE || "";

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
  async function put(path, body) {
    try {
      const r = await fetch(BASE + path, {
        method: "PUT",
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
  function setLive(field, ok) {
    if (!window._live) window._live = {};
    window._live[field] = !!ok;
  }

  // persona 映射
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

  // verify 映射
  function mapVerify(v) {
    if (!v) return null;
    const kept = (v.events_kept || 0) + (v.reminders_kept || 0) + (v.memories_kept || 0);
    const deleted = (v.events_deleted || 0) + (v.reminders_deleted || 0) + (v.memories_deleted || 0);
    const total = kept + deleted;
    const items = v.items || [];
    return {
      status: deleted > 0 ? "partial" : "passed",
      passed: kept, failed: deleted, warned: 0, total: total || 0,
      items,
    };
  }

  async function bootstrap() {
    const m = window.MockData;
    const lists = [
      ["segments", "/segments", j => j && j.segments ? j.segments : null],
      ["memories", "/memories", j => j && j.memories ? j.memories : null],
      ["events", "/events", j => j && j.events ? j.events : null],
      ["reminders", "/reminders", j => j && j.reminders ? j.reminders : null],
      ["chatLog", "/chat-log", j => j && j.chat_log ? j.chat_log : null],
      ["speakers", "/speakers", j => j && j.speakers ? j.speakers : null],
      ["wikiPages", "/wiki", j => j && j.pages ? j.pages : null],
      ["agents", "/agents", j => j && j.agents ? j.agents : null],
    ];
    await Promise.all(lists.map(async ([field, path, pick]) => {
      const j = await get(path);
      const val = pick(j);
      setLive(field, !!val);
      if (val && val.length) m[field] = val;
    }));

    // health
    const h = await get("/health");
    if (h) {
      const hh = m.health || {};
      m.health = Object.assign({}, hh, { api: "running", llm: h.llm || hh.llm, asr: h.asr || hh.asr, embedder: h.embedder || hh.embedder, speaker: h.speaker || hh.speaker, db: h.db || hh.db });
      setLive("health", true);
    }

    // persona
    const pr = await get("/profile");
    const pm = mapPersona(pr);
    setLive("persona", !!pm);
    if (pm) { pm.versions = (m.persona && m.persona.versions) || []; m.persona = Object.assign({}, m.persona, pm); }

    // verify
    const vr = await post("/verify", {});
    const vm = mapVerify(vr);
    setLive("verify", !!vm);
    if (vm) m.verifyReport = Object.assign({}, m.verifyReport, vm);

    // interventions
    const intr = await get("/interventions");
    if (intr && intr.interventions) {
      m.interventions = intr.interventions;
      setLive("interventions", true);
    }

    // recommendations
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
    return window._live;
  }

  window.PA = { BASE, get, post, put, bootstrap, updateMock, mapVerify, mapPersona, live: window._live };
})();
