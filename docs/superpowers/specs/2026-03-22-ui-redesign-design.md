# Docrawl UI Redesign — Design Specification

**Date:** 2026-03-22
**Status:** Design Phase
**Reference Mockup:** `/docs/designs/ui-redesign-mockup-v4.html`

---

## 1. Overview

### Goal
Redesign the single-file frontend (`src/ui/index.html`) with a new visual language that:
- Eliminates scroll in favor of a fixed, panel-based layout
- Unifies all 4 current theme variants (SYNTHWAVE, BASIC, TERMINAL, GLASSMORPHISM) into a single, coherent dark theme
- Exposes all API features with proper form inputs, state management, and interactive feedback
- Maintains the "no build step" constraint (inline CSS and JS only)

### Design Constraints
- **Target Resolution:** 1920×1080 minimum
- **Design Paradigm:** Desktop power tool, not mobile-first
- **Architecture:** Single HTML file with inline `<style>` and `<script>` tags
- **Font CDN:** Google Fonts (IBM Plex Mono)
- **No CSS Preprocessor:** Plain CSS with CSS variables

### Key Metrics
| Metric | Target |
|--------|--------|
| Viewport Height | 100vh fixed layout |
| Header Height | 48px (fixed) |
| Footer Height | 30px (fixed) |
| Usable Panel Height | calc(100vh - 78px) |
| Left Panel Width | 50% |
| Right Panel Width | 50% |

---

## 2. Aesthetic Direction

### Design Philosophy
Industrial and utilitarian with good taste—evoking the spirit of well-made Unix command-line tools. The design is functional, honest, and intentionally devoid of personality transmission. No decorative elements, no animations for their own sake, no visual "delight" features.

### Visual Principles
- **Purpose-driven:** Every pixel serves the interface
- **High contrast:** Text is readable from distance; hierarchy is visual, not ornamental
- **Monospace first:** All UI text uses IBM Plex Mono; no sans-serif fallback
- **Minimalist palette:** Black, gray, and a single accent color
- **No theme switcher:** Single dark theme, no variants, no user choice

### What Is Not Included
- Purple, blue-dark+white AI aesthetics
- Neon glows, bloom, or blur effects
- Gradients (except subtle background layering)
- Animations on state transitions
- Shadows (except functional elevation via borders)
- Rounded corners on functional elements (only on buttons/chips for clarity)
- Theme selector UI

---

## 3. Color Palette

All colors are CSS custom properties defined at `:root`. No hardcoded hex values in markup.

### Surfaces

| Property | Value | Usage |
|----------|-------|-------|
| `--bg` | `#0e0e0e` | Page background (visible in grid gaps) |
| `--bg-panel` | `#111111` | Primary panel backgrounds (left, right, etc.) |
| `--bg-input` | `#181818` | Input field backgrounds, raised surfaces |
| `--bg-raised` | `#1d1d1d` | Raised states (buttons on hover, chips) |
| `--bg-section` | `#0f0f0f` | Section headers, dividers |

### Borders

| Property | Value | Usage |
|----------|-------|-------|
| `--border` | `#252525` | Default borders (form inputs, panels) |
| `--border-mid` | `#333333` | Mid-weight borders (section dividers) |
| `--border-hi` | `#444444` | High-visibility borders (active elements) |

### Text

| Property | Value | Usage |
|----------|-------|-------|
| `--text` | `#e8e8e8` | Primary text (labels, body copy) |
| `--text-dim` | `#909090` | Secondary text (hints, metadata) |
| `--text-muted` | `#686868` | Tertiary text (disabled states, footers) |

### Accent (Amber)

Used **only** for: RAWL wordmark, EXECUTE button fill, pulse dot, running badge, active job ID.

| Property | Value | Usage |
|----------|-------|-------|
| `--accent` | `#c87941` | Primary action fill, running indicator |
| `--accent-dim` | `#6b3f1e` | Accent background (low contrast) |
| `--accent-hover` | `#d68f55` | Hover state on accent elements |
| `--accent-bg` | `rgba(200,121,65,0.06)` | Accent background wash |
| `--accent-text` | `rgba(200,121,65,0.80)` | Accent text overlay |

### Semantic States

| Property | Value | Usage |
|----------|-------|-------|
| `--ok` | `#5c8f5c` | Success badge, complete status |
| `--ok-dim` | `rgba(92,143,92,0.25)` | Success background wash |
| `--warn` | `#9e8638` | Warning badge, partial status |
| `--warn-dim` | `rgba(158,134,56,0.25)` | Warning background wash |
| `--err` | `#a05050` | Error badge, failed status |
| `--err-dim` | `rgba(160,80,80,0.25)` | Error background wash |
| `--info` | `#4f7a9a` | Info badge, neutral status |
| `--info-dim` | `rgba(79,122,154,0.25)` | Info background wash |

---

## 4. Typography

### Font Stack
```css
font-family: 'IBM Plex Mono', 'Courier New', monospace;
```

Import from Google Fonts CDN:
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
```

### Weight Usage

| Weight | Usage | Example |
|--------|-------|---------|
| 300 (Light) | Placeholder text, disabled labels | `font-weight: 300; opacity: 0.5;` |
| 400 (Regular) | Body text, form labels, standard UI | Default for most elements |
| 500 (Medium) | Section headers, badge text, emphasis | `font-weight: 500;` |
| 600 (Semibold) | Wordmark "RAWL", button text, control headers | `font-weight: 600;` |

### Font Sizing

| Context | Size | Line Height | Usage |
|---------|------|-------------|-------|
| Wordmark | 22px | 1 | "DOC" + "RAWL" header logo |
| Heading (Group) | 11px | 1 | "// LLM", "// Output" section headers |
| Body/Label | 13px | 1.5 | Form labels, input text, job history |
| Badge/Status | 12px | 1.2 | Status badges, chip text |
| Footer | 11px | 1.4 | Version, GitHub link |
| Tooltip | 12px | 1.4 | Hover tooltips on controls |

---

## 5. Layout Architecture

### Grid Structure

The layout uses CSS Grid with three rows (header, main, footer) and a two-column left/right panel split.

```
┌─────────────────────────────────────────────────┐ ← 48px header (fixed)
├────────────────────┬──────────────────────────┤
│  LEFT PANEL (50%)  │  RIGHT PANEL (50%)       │ ← flex: 1fr / 1fr
│  (scrollable)      │  (no scroll)             │   height: calc(100vh - 78px)
├────────────────────┴──────────────────────────┤
└─────────────────────────────────────────────────┘ ← 30px footer (fixed)
```

### Root Container

```css
body {
  display: grid;
  grid-template-rows: 48px 1fr 30px;
  grid-template-columns: 1fr;
  height: 100vh;
  width: 100vw;
  margin: 0;
  padding: 0;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
  background: var(--bg);
  overflow: hidden;
}
```

### Header (Fixed)

```css
header {
  grid-row: 1;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-mid);
  border-left: 2px solid var(--accent);
  background: var(--bg-panel);
  z-index: 100;
}
```

### Main Content Area

```css
.main {
  grid-row: 2;
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  gap: 0;
  height: 100%;
  overflow: hidden;
}
```

**Layout Breakdown:**
- Column 1: Left panel (50% width via `1fr`)
- Column 2: Divider (1px, `var(--border)`)
- Column 3: Right panel (50% width via `1fr`)

### Left Panel (Scrollable Form)

```css
.left-panel {
  grid-column: 1;
  padding: 16px;
  background: var(--bg-panel);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

/* Firefox scrollbar styling */
.left-panel::-webkit-scrollbar {
  width: 6px;
}
.left-panel::-webkit-scrollbar-track {
  background: transparent;
}
.left-panel::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}
```

### Right Panel (No Scroll)

```css
.right-panel {
  grid-column: 3;
  padding: 16px;
  background: var(--bg-panel);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
```

### Footer (Fixed)

```css
footer {
  grid-row: 3;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-top: 1px solid var(--border-mid);
  background: var(--bg-section);
  font-size: 11px;
  color: var(--text-dim);
}
```

---

## 6. Header Component

### Structure

```html
<header>
  <div class="header-left">
    <span class="wordmark">DOC<span class="wordmark-accent">RAWL</span></span>
  </div>
  <div class="header-status-indicators">
    <div class="indicator ollama-indicator">
      <span class="indicator-dot"></span>
      <span class="indicator-label">Ollama</span>
    </div>
    <div class="indicator lmstudio-indicator">
      <span class="indicator-dot"></span>
      <span class="indicator-label">LMStudio</span>
    </div>
    <div class="indicator disk-indicator">
      <span class="indicator-label">Disk: 120 GB</span>
    </div>
    <div class="indicator write-indicator">
      <span class="indicator-label">Write: OK</span>
    </div>
  </div>
</header>
```

### Wordmark Styling

```css
.wordmark {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.4em;
  color: var(--text-dim);
  font-family: 'IBM Plex Mono', monospace;
}

.wordmark-accent {
  color: var(--accent);
}
```

### Status Indicators

Each indicator shows an online/offline dot + label. Colors reflect provider status:
- **Online:** `--ok`
- **Offline:** `--err`
- **Model count:** Appended as secondary text (e.g., "Ollama (3 models)")

```css
.indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--text-dim);
  border-right: 1px solid var(--border);
}

.indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ok);
}

.indicator-dot.offline {
  background: var(--err);
}

.indicator-label {
  font-size: 11px;
  letter-spacing: 0.05em;
}
```

---

## 7. Left Panel — Form Field Inventory

The left panel organizes all configurable options into named groups (sections). Each group has a 2-column layout unless otherwise specified.

### Group: Target

**Prominence:** Highest — full width, larger font size.

```
┌─────────────────────────────────┐
│ URL Input                       │
│ https://example.com             │
└─────────────────────────────────┘
```

**Fields:**
- **URL input** (required)
  - `placeholder="https://..."`
  - `font-size: 15px`
  - Full width
  - `var(--bg-input)` background
  - `var(--border)` on all sides

**CSS:**
```css
.group-target input[type="url"] {
  width: 100%;
  padding: 8px 12px;
  font-size: 15px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
  outline: none;
  transition: border-color 150ms;
}

.group-target input[type="url"]:focus {
  border-color: var(--border-hi);
}
```

---

### Group: // LLM

**Prominence:** High — exposes model selection.

```
┌─────────────────────────────────┐
│ Provider            ▼           │
│ ┌──────────┬──────────┬────────┐│
│ │ Crawl    │ Pipeline │Reasoning││
│ │ Model ▼  │ Model ▼  │Model ▼ ││
│ └──────────┴──────────┴────────┘│
└─────────────────────────────────┘
```

**Fields:**
- **Provider select** (full width)
  - Options populated dynamically via `GET /providers` on page load
  - Response shape: `{ "providers": [{ "id": str, "name": str, "configured": bool, "requires_api_key": bool }] }`
  - Use `name` as the display label; use `configured` to optionally dim/mark unconfigured providers
  - Fallback static list if fetch fails: Ollama, LMStudio, OpenRouter, OpenCode, llama.cpp
  - JavaScript event: Populates model dropdowns on change
- **3-column grid:** `grid-template-columns: 1fr 1fr 1fr`
  - Crawl Model (select)
  - Pipeline Model (select)
  - Reasoning Model (select)

**CSS:**
```css
.group-llm-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

select {
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
  outline: none;
}

select:focus {
  border-color: var(--border-hi);
}
```

---

### Group: // Output

**Prominence:** High — controls file output.

```
┌─────────────────────────────────┐
│ ┌──────────────────┬──────────┐ │
│ │ Output Path      │ Format ▼ │ │
│ │ /home/docs   ▼   │          │ │
│ └──────────────────┴──────────┘ │
│ Language           ▼             │
│ English (en)                    │
└─────────────────────────────────┘
```

**Fields:**
- **Output Path** (2fr width) + **Output Format** (1fr width) — single row
- **Language select** (full width)

**CSS:**
```css
.group-output-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 8px;
}

.group-output input[type="text"],
.group-output select {
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
}
```

---

### Group: Controls

**Prominence:** Highest (after Target) — primary action + secondary controls.

```
┌─────────────────────────────────┐
│   ◆ EXECUTE CRAWL               │
├─────────────────────────────────┤
│ PAUSE    │ RESUME    │ CANCEL   │
└─────────────────────────────────┘
```

**Fields:**
- **EXECUTE CRAWL button** (full width)
  - 42px tall
  - `--accent` background fill
  - White or light text
  - `font-weight: 600`
  - `font-size: 13px`
  - Hover: slightly lighter (`--accent-hover`)
  - Disabled state: `opacity: 0.5`, `cursor: not-allowed`

- **Secondary controls** (3-column row: 1/3 each)
  - PAUSE, RESUME, CANCEL
  - Ghost buttons (no fill, border only)
  - Disabled by default (`disabled` attr, JS manages enabled state)
  - Text color: `var(--text-dim)` → `var(--text)` on hover

**CSS:**
```css
.btn-execute {
  width: 100%;
  height: 42px;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  background: var(--accent);
  color: white;
  border: 1px solid var(--accent);
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 150ms;
}

.btn-execute:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  flex: 1;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  transition: color 150ms, border-color 150ms;
}

.btn-ghost:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--border-mid);
}

.btn-ghost:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.controls-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  margin-top: 6px;
}
```

---

### Group: // Options

**Prominence:** Medium — optional configuration, compact 2-column grid.

All form controls in this section have `data-tooltip` attributes for inline help text.

```
┌─────────────────────────────────┐
│ ┌──────────────────┬──────────┐ │
│ │ Request Delay    │ Max      │ │
│ │ 1000             │Concurrent│ │
│ │ (ms)             │ 5        │ │
│ └──────────────────┴──────────┘ │
│ ┌──────────────────┬──────────┐ │
│ │ Max Depth        │          │ │
│ │ 10               │          │ │
│ └──────────────────┴──────────┘ │
│                                 │
│ ☑ Respect robots.txt            │
│ ☑ Filter sitemap by path        │
│ ☑ HTTP Fast-Path                │
│ ☑ Cache (24h)                   │
│ ☑ Pipeline Mode                 │
│ ☑ Native Markdown               │
│                                 │
│ Converter              ▼        │
│ html2text                       │
└─────────────────────────────────┘
```

**Fields (2-column grid where applicable):**

| Field | Type | Notes |
|-------|------|-------|
| Request Delay (ms) | number input | Min 100, max 60000, step 100 (API: `ge=100, le=60000`) |
| Max Concurrent | number input | Min 1, max 10 (API: `ge=1, le=10`) |
| Max Depth | number input | Min 1, max 20 |
| Respect robots.txt | checkbox | Has `data-tooltip` |
| Filter sitemap by path | checkbox | Has `data-tooltip` |
| HTTP Fast-Path | checkbox | Has `data-tooltip` |
| Cache (24h) | checkbox | Has `data-tooltip` |
| Pipeline Mode | checkbox | Has `data-tooltip` |
| Native Markdown | checkbox | Has `data-tooltip` |
| Converter | select | Full width |

**CSS:**
```css
.group-options {
  display: grid;
  gap: 12px;
}

.options-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.options-2col input[type="number"] {
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  cursor: pointer;
}

input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--accent);
}

.converter-select {
  width: 100%;
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
}
```

---

### Group: // Advanced (Collapsible)

**Prominence:** Low — hidden by default, expanded via JS toggle. No animation.

```
┌─────────────────────────────────┐
│ [▼] ADVANCED OPTIONS            │
├─────────────────────────────────┤
│ ☑ Skip LLM Cleanup              │
│ ☑ Markdown Proxy                │
│   Proxy URL: _______________    │
│                                 │
│ Content Selectors (max 20)      │
│ [chip] [chip] [+input]          │
│                                 │
│ Noise Selectors (max 20)        │
│ [chip] [chip] [+input]          │
│                                 │
│ Resume from State               │
│ /path/to/state.json  ▼          │
│ [RESUME]                        │
└─────────────────────────────────┘
```

**Fields:**
- **Skip LLM Cleanup** (checkbox) — `data-tooltip`
- **Markdown Proxy** (checkbox) — reveals URL input on toggle
  - **Markdown Proxy URL** (text input, initially hidden) — `data-tooltip`
- **Content Selectors** (chip input)
  - Max 20 chips
  - Enter to add
  - × button to remove
  - Placeholder: "Enter CSS selector, press Enter"
- **Noise Selectors** (chip input)
  - Max 20 chips
  - Same interaction as Content Selectors
- **Resume from State** (path input + button)
  - Text input for path
  - RESUME button (disabled if no path)

**CSS:**
```css
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  color: var(--text);
  padding: 8px 0;
  border: none;
  background: transparent;
}

.advanced-toggle::before {
  content: '▼';
  display: inline-block;
  transition: transform 150ms;
  width: 1em;
}

.advanced-toggle[aria-expanded="false"]::before {
  transform: rotate(-90deg);
}

.advanced-content {
  display: none;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.advanced-content[aria-hidden="false"] {
  display: block;
}

.chip-input-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  min-height: 32px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 11px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text-dim);
}

.chip-remove {
  cursor: pointer;
  font-weight: bold;
  color: var(--text-muted);
  transition: color 150ms;
}

.chip-remove:hover {
  color: var(--err);
}

.chip-input {
  flex: 1;
  min-width: 100px;
  padding: 4px 6px;
  font-size: 11px;
  font-family: inherit;
  background: transparent;
  border: none;
  color: var(--text);
  outline: none;
}

.chip-input::placeholder {
  color: var(--text-muted);
}
```

---

## 8. Right Panel — Activity Monitor

The right panel displays real-time crawl status and historical job information. It does not scroll.

### Section: Active Crawl Status

**Height:** ~44px (fixed).

```
┌─────────────────────────────────┐
│ ● https://example.com/page-123  │
└─────────────────────────────────┘
```

or (idle):

```
┌─────────────────────────────────┐
│ Idle                            │
└─────────────────────────────────┘
```

**Content:**
- Pulsing amber dot (●) when running, hidden when idle
- `current_url` text when running, "Idle" when no active job
- Font: 13px, weight 400

**CSS:**
```css
.active-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  height: 44px;
  background: var(--bg-section);
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  overflow: hidden;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  display: none;
}

.pulse-dot.running {
  display: block;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.current-url {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: var(--text-dim);
}

.idle-text {
  color: var(--text-muted);
}
```

---

### Section: Mission Report

**Height:** ~120px (fixed grid).

Real-time metrics from the API, displayed in a 2×2 grid:

```
┌─────────────┬─────────────┐
│      42     │      5      │
│  COMPLETE   │  PARTIAL    │
├─────────────┼─────────────┤
│       3     │      1      │
│  FAILED     │   RETRIED   │
└─────────────┴─────────────┘
```

**Metrics:**
- **COMPLETE:** `pages_completed` from `JobStatus` / SSE events
- **PARTIAL:** Tracked client-side from SSE `phase_change` events (pages that completed with partial extraction — requires implementation to count from event payload; `pages_partial` does not exist in `JobStatus` today)
- **FAILED:** Tracked client-side from SSE `phase_change` events (pages that errored — `pages_failed` does not exist in `JobStatus` today)
- **RETRIED:** `pages_retried` from `JobStatus`

> **Implementation note:** `pages_partial` and `pages_failed` are absent from the `JobStatus` Pydantic model and therefore not returned by `GET /jobs/{id}/status`. However, they **are already emitted** by the runner in the `job_done` SSE event payload (`runner.py` lines 825–826). The UI should populate PARTIAL and FAILED from the `job_done` event. No backend changes are required for the initial implementation. Adding these fields to `JobStatus` is a separate improvement (deferred).

**CSS:**
```css
.mission-report {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 16px;
  background: var(--bg-section);
  border-bottom: 1px solid var(--border);
}

.metric-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
}

.metric-number {
  font-size: 30px;
  font-weight: 600;
  color: var(--text);
  line-height: 1;
  margin-bottom: 4px;
}

.metric-label {
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}
```

---

### Section: Job History

**Height:** Remaining space, scrollable internally if needed.

```
┌─────────────────────────────────┐
│ Search... ▌                     │
├─────────────────────────────────┤
│ #abc12 ● https://ex.com 14:30  │
│ #def34 ✓ https://ex.com 13:15  │
│ #ghi56 ✕ https://ex.com 12:00  │
└─────────────────────────────────┘
```

**Components:**
1. **Filter input** (full width, optional)
   - Placeholder: "Search job ID or URL..."
   - Filters job list by ID substring or URL substring
2. **Job list** (scrollable internally)
   - Each row: ID (badge) | Status (colored badge) | URL (truncated) | Timestamp
   - Status badges: ● (running/amber), ✓ (complete/green), ✕ (failed/red), ⚠ (partial/yellow)
   - Colors use semantic state variables: `--ok`, `--err`, `--warn`, `--info`

**CSS:**
```css
.job-history {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.job-history-filter {
  padding: 8px 12px;
  font-size: 12px;
  font-family: inherit;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-bottom: 1px solid var(--border-mid);
  color: var(--text);
}

.job-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.job-item {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  cursor: pointer;
  transition: background-color 150ms;
}

.job-item:hover {
  background: var(--bg-raised);
}

.job-id {
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 500;
  color: var(--accent);
  min-width: 60px;
}

.job-status-badge {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.job-status-badge.complete {
  background: var(--ok);
}

.job-status-badge.partial {
  background: var(--warn);
}

.job-status-badge.failed {
  background: var(--err);
}

.job-status-badge.running {
  background: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}

.job-url {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-dim);
  font-size: 11px;
}

.job-timestamp {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
```

---

## 9. Footer Component

Fixed 30px footer with version info on the left and model credits on the right.

```
┌─────────────────────────────────┐
│ v1.2.3 • GitHub            Models: qwen3, llama2 │
└─────────────────────────────────┘
```

**Content:**
- **Left:** Version number + GitHub link. Version fetched from `GET /info` (`version` field) on page load and injected into the footer DOM. No `window.DOCRAWL_VERSION` — set directly on the element.
- **Right:** "Models used: [comma-separated list]"

**CSS:**
```css
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 30px;
  background: var(--bg-section);
  border-top: 1px solid var(--border-mid);
  font-size: 11px;
  color: var(--text-dim);
}

footer a {
  color: var(--accent);
  text-decoration: none;
  transition: color 150ms;
}

footer a:hover {
  color: var(--accent-hover);
}

.footer-version {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-models {
  font-size: 10px;
  color: var(--text-muted);
}
```

---

## 10. Tooltips

### Implementation Strategy

Tooltips are **not** CSS `::after` pseudo-elements. Instead, they are JavaScript-generated `<div>` elements appended to the document body, allowing them to escape the `overflow: hidden` constraint on the right panel.

### Structure

```html
<div class="tooltip" style="position: fixed; top: 100px; left: 200px;">
  Maximum number of concurrent requests
</div>
```

### Behavior
- **Trigger:** `mouseenter` on any element with `data-tooltip` attribute
- **Position:** Positioned relative to the trigger element, with margin for clearance
- **Hide:** `mouseleave`, or after 5 seconds of inactivity
- **Content:** Value of `data-tooltip` attribute
- **Style:** Small gray box, 200px max-width, 12px font, subtle border

### CSS

```css
.tooltip {
  position: fixed;
  max-width: 200px;
  padding: 6px 10px;
  font-size: 11px;
  background: var(--bg-raised);
  border: 1px solid var(--border-mid);
  color: var(--text-dim);
  border-radius: 3px;
  z-index: 10000;
  pointer-events: none;
  word-wrap: break-word;
  line-height: 1.4;
}
```

### JavaScript Handler

```javascript
document.addEventListener('mouseenter', function(e) {
  const target = e.target.closest('[data-tooltip]');
  if (!target) return;

  const tooltip = document.createElement('div');
  tooltip.className = 'tooltip';
  tooltip.textContent = target.dataset.tooltip;
  document.body.appendChild(tooltip);

  const rect = target.getBoundingClientRect();
  tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
  tooltip.style.top = (rect.top - tooltip.offsetHeight - 6) + 'px';

  const hideTooltip = () => {
    tooltip.remove();
    target.removeEventListener('mouseleave', hideTooltip);
  };

  target.addEventListener('mouseleave', hideTooltip);
}, true);
```

---

## 11. Interactivity & State Management

### Advanced Section Toggle

The Advanced section is **not animated**—it is shown/hidden instantaneously via `display` and `aria-hidden` attributes. This avoids layout thrashing and is appropriate for a dense tool UI.

```javascript
const advancedToggle = document.querySelector('.advanced-toggle');
const advancedContent = document.querySelector('.advanced-content');

advancedToggle.addEventListener('click', () => {
  const isExpanded = advancedToggle.getAttribute('aria-expanded') === 'true';
  advancedToggle.setAttribute('aria-expanded', !isExpanded);
  advancedContent.setAttribute('aria-hidden', isExpanded);
});
```

### Markdown Proxy URL Reveal

The "Markdown Proxy" checkbox toggles visibility of a URL input field directly below it.

```javascript
const markdownProxyCheckbox = document.querySelector('input[name="markdown_proxy"]');
const markdownProxyUrlField = document.querySelector('.markdown-proxy-url-wrapper');

markdownProxyCheckbox.addEventListener('change', () => {
  markdownProxyUrlField.style.display = markdownProxyCheckbox.checked ? 'block' : 'none';
});
```

### Chip Input Interaction

Chip inputs accept text input and emit chips on Enter. Chips display an × button for removal.

```javascript
document.querySelectorAll('.chip-input').forEach(input => {
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const value = input.value.trim();
      if (value && !input.dataset.maxExceeded) {
        addChip(input.closest('.chip-input-container'), value);
        input.value = '';
      }
    }
    if (e.key === 'Escape') {
      input.value = '';
    }
  });
});
```

### Job SSE Event Handling

Pause, Resume, and Cancel buttons are enabled/disabled based on active job state from SSE events.

```javascript
// SSE event types from runner.py: 'phase_change', 'log', 'job_done'
//
// job_done payload shape (runner.py lines 820-838):
//   { status, pages_ok, pages_partial, pages_failed, pages_retried, ... }
// Note: pages_partial and pages_failed ARE available in the job_done payload
// even though they are absent from JobStatus model — use them here.

eventSource.addEventListener('job_done', (e) => {
  const data = JSON.parse(e.data);
  updateControlButtons(data.status);
  updateMissionReport(data);  // populate PARTIAL and FAILED from job_done payload
});

// Pause/Resume do NOT emit job_done — poll status immediately after API call
async function pauseJob(jobId) {
  await fetch(`/api/jobs/${jobId}/pause`, { method: 'POST' });
  const status = await fetch(`/api/jobs/${jobId}/status`).then(r => r.json());
  updateControlButtons(status.status);
}

async function resumeJob(jobId) {
  await fetch(`/api/jobs/${jobId}/resume`, { method: 'POST' });
  const status = await fetch(`/api/jobs/${jobId}/status`).then(r => r.json());
  updateControlButtons(status.status);
}

function updateControlButtons(status) {
  if (status === 'running') {
    document.querySelector('.btn-pause').disabled = false;
    document.querySelector('.btn-resume').disabled = true;
    document.querySelector('.btn-cancel').disabled = false;
  } else if (status === 'paused') {
    document.querySelector('.btn-pause').disabled = true;
    document.querySelector('.btn-resume').disabled = false;
    document.querySelector('.btn-cancel').disabled = false;
  } else { // completed, failed, cancelled
    document.querySelector('.btn-pause').disabled = true;
    document.querySelector('.btn-resume').disabled = true;
    document.querySelector('.btn-cancel').disabled = true;
  }
}

function updateMissionReport(data) {
  // pages_partial and pages_failed come from job_done SSE payload (runner.py:825-826)
  // pages_completed and pages_retried also available from JobStatus polling
  document.getElementById('stat-complete').textContent = data.pages_ok ?? 0;
  document.getElementById('stat-partial').textContent  = data.pages_partial  ?? 0;
  document.getElementById('stat-failed').textContent   = data.pages_failed   ?? 0;
  document.getElementById('stat-retried').textContent  = data.pages_retried  ?? 0;
}
```

---

## 12. API Gap Fixes in This Redesign

The following API features are **newly exposed** in the UI:

| Feature | Endpoint | Input/Control | Notes |
|---------|----------|----------------|-------|
| Markdown Proxy URL | `POST /jobs` (`use_markdown_proxy` + `markdown_proxy_url` fields) | Checkbox + URL input (hidden by default) | Both fields sent in job request body |
| Skip LLM Cleanup | `POST /jobs` (`skip_llm_cleanup` field) | Checkbox | Advanced section |
| Content Selectors | `POST /jobs` (`content_selectors` field) | Chip input | Advanced section, max 20 items |
| Noise Selectors | `POST /jobs` (`noise_selectors` field) | Chip input | Advanced section, max 20 items |
| Pause Job | `POST /jobs/{id}/pause` | Button | Only enabled when job running |
| Resume Job | `POST /jobs/{id}/resume` | Button | Only enabled when job paused |
| Resume from State | `POST /jobs/resume-from-state` | Path input + button | Advanced section |
| Current URL | (SSE event) | Display only | Active crawl strip |
| Pages Retried | (API response) | Display only | Mission Report grid |

---

## 13. What Is Removed

The following elements from the current UI are **not carried forward**:

| Removed | Reason |
|---------|--------|
| SYNTHWAVE theme | Consolidated into single industrial theme |
| BASIC theme | Consolidated into single industrial theme |
| TERMINAL theme | Consolidated into single industrial theme |
| GLASSMORPHISM theme | Consolidated into single industrial theme |
| Theme selector dropdown | Single theme only |
| `use_page_pool` checkbox | Deprecated per issue #201 |
| Decorative scanlines | Not appropriate for utilitarian design |
| Neon glow effects | Removed per aesthetic guidelines |
| Blur/backdrop-filter effects | Removed for clarity and performance |

---

## 14. Implementation Notes

### File Structure
```
src/ui/index.html  (single file, no build step)
├── <meta> + <link> to Google Fonts CDN
├── <style> (inline CSS)
│   ├── CSS variables (:root)
│   ├── Layout (grid, flexbox)
│   ├── Components (header, panels, buttons, etc.)
│   └── Animations (pulse only)
└── <script> (inline JavaScript)
    ├── Initialization on DOMContentLoaded
    ├── Event listeners (form, SSE, etc.)
    ├── Tooltip handler
    └── Chip input manager
```

### No Build Step
- No bundler (Webpack, Vite, etc.)
- No transpiler (TypeScript, Babel, etc.)
- No CSS preprocessor (SASS, PostCSS, etc.)
- All code is valid HTML5 + CSS3 + ES6

### CSS Custom Properties Usage
All colors and sizing are defined as `:root` CSS variables. This allows future theme variants (if needed) via JavaScript class switching without code changes.

Example variable update:
```javascript
document.documentElement.style.setProperty('--accent', '#ff6b00');
```

### Accessibility Considerations
- Semantic HTML: `<button>`, `<input>`, `<select>`, `<label>`
- ARIA attributes: `aria-expanded`, `aria-hidden`, `aria-label` where needed
- Keyboard navigation: Tab order, Enter for submit, Escape for cancel
- Focus styles: Visible outline on interactive elements
- Contrast: All text meets WCAG AA (4.5:1 minimum)
- Screen reader support: Tooltips exposed via `aria-label` fallback

### Performance
- Single file: No HTTP round-trips for assets
- No animations on critical path
- Pulse animation uses `will-change` optimization
- Scrollbar is thin (`scrollbar-width: thin`) to reduce visual weight
- Grid layout is GPU-accelerated

### Browser Support
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- No IE support

---

## 15. Reference Mockup

A visual reference mockup is available at `/docs/designs/ui-redesign-mockup-v4.html`. This mockup demonstrates:
- Exact layout proportions (50/50 split)
- Color application across all components
- Typography hierarchy
- Form field grouping
- Status indicator positioning
- Job history list styling

This specification is binding for implementation. Deviations must be approved by the design lead.

---

**Document Version:** 1.0
**Last Updated:** 2026-03-22
**Status:** Ready for Implementation
