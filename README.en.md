<p align="center">
  <img src=".github/assets/hero.svg" width="100%" alt="The Negative Space of Memory — a memory system that moves you" />
</p>

<h1 align="center">The Negative Space of Memory</h1>

<p align="center">
  <b>Memory That Belongs to Humans · A memory system that moves you</b><br />
  <sub><i>The age of retrieval has already been cleared. We are building the next thing: when a memory carries weight, how should a system respond.</i></sub>
</p>

<p align="center">
  <a href="README.md">中文</a> ·
  <a href="#what-the-system-looks-like">System</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="web/design-system/DESIGN.md">Design Language "Growth Rings · Ink"</a> ·
  MIT License
</p>

---

## One Problem Already Solved — and One Nobody Has Tackled

For the past decade, almost every memory system has been answering the same question: **how to find it back.**
Vector stores, knowledge graphs, hybrid recall, RAG — this race has already been won.
This project's retrieval layer (hybrid recall + entity graph + voiceprint archiving) is itself a long-mature capability. It is the foundation, but no longer the story.

What nobody has seriously worked on is the next question:

> **When a person speaks aloud the heaviest memory of their life,**
> **what should a system that "remembers everything" say, not say — and when should it fall silent.**

This is where the project believes the revolution lies: **the second half of memory systems is not retrieval — it is negative space.**

## Negative Space: The Breath of Memory

The blank in a Chinese painting is never something left unfinished; it is where the picture breathes.
Memory systems are the same — **their quality is not decided by "how much is remembered", but by "how restrainedly the memory is used".**

A memory system that pours everything out is an offense: at your most fragile moment, it quotes precisely every word you ever said, like presenting evidence.

This system chooses to do the opposite:

- **Selective return** — memories do not rush in uninvited; they are gently placed back in front of you only at the moment they truly belong.
- **Narrative over data** — volume was never the issue; the issue is the narrative and understanding of a moment. One understood moment outweighs ten thousand indexed records.
- **Knowing what not to say** — the system reserves the right to silence. Not everything remembered deserves to be brought up; negative space is respect, not omission.
- **No performed empathy** — no exclamation-mark warmth, no sentimentality disguised as human. Present, but never intrusive.

## Responding to the Heaviest Moments

Everyone carries a few memories they dare not touch lightly: people who are gone, places they cannot return to, words never said.
When they surface in conversation, this system follows only four rules of conduct:

1. **Be present first, respond second.** No retrieval, no recommendations, no "you might also like". In that moment the system's only task is to catch the sentence.
2. **Treat memory as relic, not data.** Important moments are sealed with vermilion — marked as unrewritable evidence, never entering any "optimization" or "cleanup".
3. **Return, don't recite.** At the right moment years later, hand back the details of that day untouched — you thought you had forgotten, yet it was still there; it kept it for you all along.
4. **Silence, honestly.** When there are no fitting words, say nothing. The blank is itself a kind of response.

## The Value AI Ultimately Brings to Humans

This project has a definite answer to "the value of AI":

**Not making people faster, but making sure no one has to carry their memories alone.**

Efficiency was the task the industrial age handed to AI. But when a machine can truly remember everything,
the only use worthy of human trust is keeping watch, on humanity's behalf, over the things we **cannot bear to forget, yet dare not look at often** —
and gently returning them at the right moment across the long years.

When technology is taken to its end, all that remains is tenderness.

---

## What the System Looks Like

Memory is treated as a living tree: one growth ring = one period of life, ring width = memory density, concentric layers = closeness of relationships, vermilion = sealed as unrewritable evidence.

```text
Recording / transcript / text
   → inbox feeding (ink dropped into water)
   → narrative pipeline: segments → moments (moments.db) → people & relationships (people.db) → wiki entity graph
   → retrieval layer (hybrid recall + vector + graph) — a foundation already cleared, appearing only when needed

Frontend: Web (Growth Rings · Ink design language) / Android / ESP32-S3 recording firmware / desktop overlay shell
Backend: Memory That Belongs to Humans · single FastAPI process · SQLite / DuckDB · switchable local LLM (stub / ollama / openai_compat)
Voiceprint: local MFCC voiceprint store → stable "voiceprint → role" mapping across recordings (voiceprint.py)
```

The design system is a standard **OpenDesign package** (`web/design-system/`, od-design-system-project/v1):
porcelain-white paper + pine-soot ink lines + vermilion seals, motion contract "Growth and Fracture". Single source of truth: [design-system/DESIGN.md](web/design-system/DESIGN.md).

## Memory System Structure

Memory is not a single store but an integrated structure of "three core layers + a two-layer fusion".

### Three Core Layers: From Evidence to Self-Narrative

This three-layer structure is not a borrowed framework but a complete answer rebuilt from first principles: segments are evidence, L1 is understood memory, L2 is the narrative of a period, L3 is the system's self-narrative of you — every layer serves "response", not "retrieval".

| Layer | Table | Stores | Key fields |
|---|---|---|---|
| Raw segment layer | `segments` | transcript/text segments | time span, speaker, `time_kind` (received = record time / occurred = real event time) |
| L1 memory | `memories` | one understood memory | `content`, verbatim `evidence`, `embedding`, `priority` 0–100 importance, `version` dedup-merge version |
| L2 scene | `scenes` | narrative of a period/scene | `summary`/`body`, `heat`, `source_mem_ids` traceable to L1 |
| L3 persona | `persona_versions` | versioned narrative profiles | ≤2000-char narrative, `change_summary` |
| Voiceprint layer | `speakers` | MFCC voiceprint vectors | stable "voiceprint → role" mapping across recordings |

### Fused Memory Layer (Bridge Contract)

The system is one body made of two layers: the conversational-perception layer (this repo's backend) and the fused memory layer (information layer + moment layer). They are joined through `memory_bridge.py` by two contracts:

- **Read-only consumption** — information layer `cockpit.db` (wiki_pages) + L1 summary md + `content/` originals; moment layer `moments.db` (`verbatim_quote` / `narrative` / `tags` / `recalled`).
- **Single intake, dual-head extraction** — the write path only drops into `inbox/`; the fused layer's `cycle.sh` performs the two-layer extraction; the conversational-perception layer never writes directly to any fused-layer DB.

### Retrieval: A Foundation Already Cleared

Hybrid retrieval = FTS5 bigram + vector gateway (auto-degrades when offline) + RRF fusion + GA three-dimensional final ranking; locally, a full numpy cosine in-memory load (MVP scale). Retrieval appears only when needed — this is "negative space" implemented at the engineering layer.

## Development Board (ESP32-S3)

| Item | Description |
|---|---|
| Board | `genjutech-s3-1.54tft` (ESP32-S3 + 1.54" TFT), firmware `boards/` directory |
| Firmware project | `scripts/xiaozhi-esp32/` (based on xiaozhi-esp32) + `components/background_audio/` |
| Current form | pure recording device (v0.12 trim): mic capture + background audio streaming, PCM → `ws://<pc>:<port>/ws/audio` |
| Removed | real-time dialogue / TTS / wake word / MCP |
| Kept | display status feedback, protocol base class, background_audio, LED, OTA, settings, system_info |
| Config | `sdkconfig.defaults.esp32s3` (wake-word TTS off); power-saving sleep forbidden during streaming |
| Build | `scripts/build-idf.py` + `build-local.*`; GitHub Actions ESP-IDF container cloud build; `qemu-test.ps1` |

## Project Architecture

```text
Clients  Web (Next.js static export, backend serves web/dist) / Android / ESP32-S3 / desktop overlay shell (Electron, connect-only)
   ↓ HTTP / WS :8004
Memory That Belongs to Humans · single FastAPI process
   ├─ Dialogue & orchestration   chat / proactive / recommend / reminders / calendar
   ├─ Memory                     memory_bridge (fused read-only + inbox intake) / storage (local three layers) / verify (anti-hallucination)
   ├─ Perception                 asr / voiceprint / temporal / transcript / ingest
   ├─ Expression                 speaker / assistant_personality (versioned persona, separate from the user profile)
   └─ Config                     config / llm / llm_upstream (one-click upstream sync for the whole project) / auth
   ↓
Storage  SQLite (segments/memories/scenes/persona_versions/interventions/kv/speakers) + DuckDB (ASR intermediate)
   ⇣ read-only
Fused memory layer  cockpit.db (wiki information layer) / moments.db (moment layer) / memory.db (profile & complexity metrics) — part of the same system as the layers above
```

Backends are switchable (`config/default.yaml` + runtime `/settings/llm` hot-change; local failures raise explicit errors and never silently fall back to the cloud):

| Component | dev | prod |
|---|---|---|
| ASR | `stub` | `faster_whisper` (large-v3, CUDA) |
| LLM | `stub` / `anthropic_proxy` | `ollama` / `openai_compat` / `deepseek` / `glm_anthropic` |
| Embedder | `hashing` | `openai_compat` |
| Speaker | `text` | local TTS |

## Implementation Highlights

- **Anti-hallucination (verify.py)**: a mandatory re-check after every LLM extraction step — time is authoritatively re-resolved by deterministic `temporal` rules, and LLM-fabricated dates are deleted outright; `when_raw` must land verbatim in the source transcript or a date equivalent; a memory's `evidence/segment_id` must exist and its content must be bigram-traceable. **Every conclusion can be traced back to a real transcript.**
- **View of time (temporal.py)**: distinguishes received (record time) from occurred (real event time); without a device timestamp it admits unavailability instead of guessing.
- **Voiceprint (voiceprint.py)**: MFCC mean+std vectors are stored; within the cosine threshold a speaker maps to a role, outside it is marked unknown; only 16-bit PCM WAV — other formats are transcoded when ffmpeg is present, otherwise single-file diarize only: degrade, but never error.
- **Dedup & merge**: `memories.version` increases monotonically to keep update/merge provenance; `priority` 0–100 is L1 importance.
- **Unified upstream (llm_upstream.py)**: one-click sync of the two LLM configurations (fused layer and conversational-perception layer), eliminating "the same upstream written twice in two places".
- **Tests**: pytest + stub-backend end-to-end (`PA_LLM_BACKEND=stub …`), 23+ evergreen checks including render guards.

## Complexity Metrics Methodology

The profile page's "Complexity Metrics" and "Metrics Explained" come from `memcore/metrics.py`, with the methodological contract written in `web/lib/metrics-science.ts`: **every metric must answer five things** — provenance (paper/author/year), what it intuitively measures, the formula, how to read it, and validity (how the null baseline is built / how CIs are computed / the reporting threshold / known limitations).

Nineteen metrics in five groups:

| Group | Metrics |
|---|---|
| Temporal rhythm | `circadian_strength` (1 − H(24h histogram)/ln24), `weekly_rhythm`, `burstiness_global/person`, `inter_event_alpha` |
| Social structure | `signature_shares`, `dunbar_layers`, `social_entropy`, `contact_diversity` |
| Complex dynamics | `sample_entropy`, `permutation_entropy`, `dfa_alpha`, `rqa`, `hmm_states`, `ews_autocorr` |
| Language & content | `attention_zipf`, `topic_entropy` |
| Network | `cooccurrence_network`, `multiplex_pagerank` |

Three iron rules of validity:

1. **Permutation null baseline** — e.g. circadian permutes the within-day clock 600 times, one-sided greater; no number is reported if it is not significantly different from random.
2. **Confidence intervals travel with values** — delete-one-day jackknife etc.; every value carries `ci_low/ci_high/n`.
3. **Reporting threshold** — below the threshold the metric is greyed out with a reason (e.g. messages ≥200 and days ≥20); **no fabricated numbers**.

The explainer page covers methodology only and shows no personal figures; personal values and their eligible / ineligible_reason live in the "Complexity Metrics" tab (metric table: value / ci / n / null_baseline / params).

---

## Quick Start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
# Configure .env (at least set PA_API_TOKEN in production)
python3 -m personal_assistant.cli serve --host 127.0.0.1 --port 8004
# Open http://127.0.0.1:8004/web/
```

(The CLI module name `personal_assistant` is a legacy identifier; the product is named "Memory That Belongs to Humans".)

Isolated end-to-end verification (no real models required):

```bash
PA_LLM_BACKEND=stub PA_ASR_BACKEND=stub PA_SPEAKER_BACKEND=text python3 -m personal_assistant.cli test
```

Drop recording transcripts `.txt` into `data/inbox/`, then `cli pipeline --once` turns them into stored segments; for real audio set `PA_ASR_BACKEND=faster_whisper`.
See the in-repo docs for the ESP32-S3 recording firmware, the desktop overlay shell, and more configuration.

## License

MIT — memories belong to everyone, and so should the tools.
