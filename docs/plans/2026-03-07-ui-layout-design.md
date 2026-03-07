# UI Layout Improvement — Design Doc

**Date:** 2026-03-07
**Scope:** Option A — surgical layout fixes to `src/ui/index.html`
**Target resolution:** 1920×1080 (primary), degrades cleanly to ≤1100px
**Approach:** Minimal, targeted changes. No CSS refactor, no new files.

---

## Problem Statement

At 1920×1080 the current layout has:
- Container capped at 1200px → 360px of wasted space on each side (37% of viewport unused)
- Two equal columns (`flex`) → right column (job history) renders at only 250px tall when no job is active, leaving a large void
- "Execute Crawl" button duplicated: `#startBtn` in the form + `#startBtnRight` in the right column — both visible simultaneously at wide viewports
- Right column is not sticky → the output log scrolls off screen as the form is used
- Full page scrolls (1647px) instead of right panel scrolling independently

Validated with Playwright screenshots at 1920×1080 across 6 layout variants (see `ui-experiments/`).

---

## Design Decisions

### 1. Container width

```css
.container {
    max-width: min(1600px, calc(100vw - 48px));
}
```

- **1600px** at 1920 → 160px margin per side (comfortable breathing room, not wasteful)
- `min()` ensures it degrades gracefully at any viewport without needing extra media queries
- Chosen over 1400px (still wastes 260px/side) and 1700px (too close to edge)

### 2. Grid — 65/35 split

```css
.two-columns {
    display: grid;
    grid-template-columns: 65% 35%;
    gap: 32px;
    align-items: start;
}
```

- Left (form): ~1040px — plenty of space for inputs and labels
- Right (output): ~560px — enough for job history list + log entries without wrapping
- `align-items: start` prevents the right column from stretching to match left column height
- Tested variants: 55/45, 60/40, 65/35 → 65/35 selected as it matches the usage ratio (form is primary, output is secondary)

### 3. Sticky right column

```css
.right-column {
    position: sticky;
    top: 16px;
    max-height: calc(100vh - 80px);
    overflow-y: auto;
}
```

- Output panel stays in view while the form scrolls — critical for monitoring long crawl jobs
- `max-height` prevents overflow beyond viewport; internal scroll handles long log output
- Reverted to `static` at ≤1100px breakpoint (single column, sticky doesn't make sense)

### 4. Breakpoint

```css
@media (max-width: 1100px) {
    .two-columns { grid-template-columns: 1fr; }
    .right-column { position: static; max-height: none; }
}
```

- New breakpoint at 1100px, above the existing 900px and 600px breakpoints
- Between 1100–900px: single column but still full-width inputs
- Below 900px: existing responsive styles take over unchanged

### 5. Execute button — moved up, duplicate removed

**New form order:**
```
URL input
Depth / Max pages / Concurrency
Model selection (crawl + pipeline + reasoning)
▶ EXECUTE CRAWL   ← moved here (before advanced options)
─────────────────────────────────────
Advanced options (fast-path, sitemap, dedup, etc.)
■ ABORT
```

Rationale: the primary action should be reachable without scrolling past all advanced options. Advanced options remain visible and editable, just below the button.

**Duplicate removed:**
- Delete `#startBtnRight` and `#cancelBtnRight` from HTML (lines ~1311–1313)
- Delete their event listeners from JS (`startBtnRight.addEventListener`, `cancelBtnRight.addEventListener`)
- Delete `.right-column .buttons` CSS rule (line ~197)

### 6. Right panel empty state — collapsed (Option B)

```css
.job-history-panel {
    min-height: 0;
    transition: min-height 0.2s ease;
}
.job-history-empty {
    padding: 1rem;
    color: var(--text-dim);
    font-size: 0.85rem;
}
```

No forced height when empty. Panel shows a small "No jobs yet" label and grows naturally as jobs appear. Avoids the large void in the right column on first load.

---

## Out of Scope

- CSS refactor / extraction to separate file (Option B from brainstorm — future PR)
- New themes (deferred — layout stabilizes first)
- Changes to any theme other than adjusting container/grid (all three themes — synthwave, basic, terminal — inherit the layout changes automatically via shared classes)

---

## Files Changed

| File | Change |
|------|--------|
| `src/ui/index.html` | CSS: container width, grid columns, sticky right, empty state, breakpoint |
| `src/ui/index.html` | HTML: remove `#startBtnRight` / `#cancelBtnRight`, reorder form buttons |
| `src/ui/index.html` | JS: remove `startBtnRight` / `cancelBtnRight` listeners |

Single file, no new dependencies.

---

## Verification

After implementation, verify with Playwright at:
- 1920×1080 — container uses 1600px, 65/35 grid, right column sticky
- 1440×900 — container fills width, layout holds
- 1100px viewport — breakpoint triggers, single column
- 900px viewport — existing responsive styles unchanged
- With job running — right panel sticky, log scrollable, no duplicate button
- Empty state — right panel collapses, no large void
