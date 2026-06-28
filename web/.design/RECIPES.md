<!-- onedayassets:design-recipes v1 -->
# Design Recipes — on-demand technical reference

Read this file only when a task actually needs one of the recipes below.
These are implementation mechanics, not design judgment — the craft rules
live in your main system prompt, the binding hard rules in the contract.

## Tweaks panel — host-message protocol & storage

The Tweaks panel is produced by the `tweaks` runtime skill, not hand-written.
You only need the mechanics below when patching a hand-edited panel after the
fact — for any new prototype, let the skill emit the code so the contract
(visibility / EDITMODE block / storage binding) stays in lockstep with the host.

The installed snippet already:
- Listens for `__activate_edit_mode` / `__deactivate_edit_mode` to show/hide the
  panel AFTER first paint (initial state is always visible).
- Posts `__edit_mode_available` so the toolbar toggle appears.
- Posts `__edit_mode_set_keys` on every value change so the host can write edits
  back to disk.

State persists to a per-artifact `localStorage` key `tweaks-<artifact-slug>` —
never shared across prototypes in different tabs. Defaults are wrapped in exactly
one `var TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{ ... }/*EDITMODE-END*/;` block per
root HTML file, and that block MUST be valid JSON (the host parses it to merge
edits back to disk). Use `var` (not `const`) to avoid re-declaration errors when
the preview host replays scripts.

## React + Babel (inline JSX)

When writing React prototypes with inline JSX, use these EXACT pinned
versions. Never use unpinned versions (e.g. `react@18`).

```html
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.26.0/babel.min.js" crossorigin="anonymous"></script>
```

Import helper/component scripts via plain `<script>` tags. Avoid
`type="module"` on script imports — it may break things.

CRITICAL: do NOT create module dependencies that are not written to disk.
Inline JSX prototypes default to code inside the main HTML file; app.tsx
prototypes default to only `app.tsx`. Do not write `import './PolaroidScheme'`,
`import Button from './Button'`, or similar new paths unless you actually
created the matching root-level file (per HARD RULE 3, no subfolders —
`import Button from './components/Button'` is doubly forbidden). For small
variants, color schemes, mock data, or helper functions, inline them as
objects, arrays, or functions.

CRITICAL: when defining global-scoped style objects, give them SPECIFIC
names. If you import >1 component with a `styles` object, it will break.
Give each styles object a unique name based on the component, like
`const terminalStyles = { ... }`, OR use inline styles. NEVER write
`const styles = { ... }`. Name collisions cause breakages — non-negotiable.

CRITICAL: with multiple Babel script files, components don't share scope.
Each `<script type="text/babel">` gets its own scope when transpiled. To
share components between files, export them to `window` at the end of your
component file:

```js
// At the end of components.jsx:
Object.assign(window, {
  Terminal, Line, Spacer,
  Gray, Blue, Green, Bold,
  // ... all components that need to be shared
});
```

This makes components globally available to other scripts.

## Animations (video-style HTML artifacts)

- Interactive prototypes: CSS transitions or simple React state is fine.
- Motion-design / video-style artifacts: hand-roll a `requestAnimationFrame`
  timeline (or pin a small animation lib from a CDN) — keep all timing logic
  inside the single HTML file, no build step.

## Speaker notes for decks

NEVER add speaker notes unless the user explicitly asks. When asked, put less
text on slides and focus on impactful visuals; write speaker notes as full
scripts in conversational language. In `<head>`, add:

```html
<script type="application/json" id="speaker-notes">
[
    "Slide 0 notes",
    "Slide 1 notes"
]
</script>
```

The page MUST call `window.postMessage({slideIndexChanged: N})` on init and on
every slide change so speaker notes stay in sync with the current slide.

## Fixed-size content (slides / decks / videos)

Slide decks, presentations, videos and other fixed-size content must implement
their own JS scaling so the content fits any viewport: a fixed-size canvas
(default 1920×1080, 16:9) wrapped in a full-viewport stage that letterboxes it
on black via `transform: scale()`, with prev/next controls OUTSIDE the scaled
element so they stay usable on small screens.

For slide decks specifically, build a small reusable shell: each slide is a
direct child `<section>` of a stage wrapper, with keyboard/tap navigation, a
slide-count overlay, localStorage persistence of the current index,
print-to-PDF (one page per slide), `data-screen-label` on every slide, and a
`{slideIndexChanged: N}` postMessage on each navigation so speaker notes stay
in sync.

## Reading `<mentioned-element>` blocks

When the user comments on, inline-edits, or drags an element in the preview,
the attachment includes a `<mentioned-element>` block — a few short lines
describing the live DOM node they touched. Use it to infer which source-code
element to edit. Ask the user if unsure how to generalize. It can contain:
- `react:` — outer→inner chain of React component names from dev-mode fibers
- `dom:` — dom ancestry
- `id:` — a transient attribute stamped on the live node (`data-cc-id="cc-N"`
  in comment/knobs/text-edit mode, `data-dm-ref="N"` in design mode). This is
  NOT in your source — it's a runtime handle.

When the block alone doesn't pin down the source location, read the source
files around the dom/react chain to disambiguate before editing.
Guess-and-edit is worse than a quick re-read.

## Labelling slides and screens for comment context

Put `[data-screen-label]` attrs on elements representing slides and high-level
screens; these surface in the `dom:` line of `<mentioned-element>` blocks so
you can tell which slide or screen a comment is about.

Slide numbers are 1-indexed. Use labels like "01 Title", "02 Agenda" —
matching the slide counter (`{idx + 1}/{total}`) the user sees. When a user
says "slide 5", they mean the 5th slide (label "05"), never array position [4].
If you 0-index your labels, every slide reference is off by one.
