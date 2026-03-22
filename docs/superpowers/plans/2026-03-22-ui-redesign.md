# Docrawl UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `src/ui/index.html` as a single-file industrial dark-theme UI that eliminates scroll, removes all 4 legacy themes, and exposes all API features.

**Architecture:** Single HTML file with inline `<style>` and `<script>` — no build step, no external assets except Google Fonts CDN. CSS Grid layout: `48px header / 1fr main / 30px footer`, 100vh, no page scroll. Left panel scrolls internally; right panel is overflow-hidden.

**Tech Stack:** HTML5, CSS3 (custom properties), ES6 vanilla JS, IBM Plex Mono (Google Fonts CDN). Backend: FastAPI at `/api/` prefix.

**Reference Mockup:** `docs/designs/ui-redesign-mockup-v4.html` — approved visual blueprint. Port structure and CSS from it, then wire to real API.

---

## Pre-flight: Key API Facts

All endpoints are prefixed `/api/`:

| Endpoint | Method | Usage |
|----------|--------|-------|
| `/api/info` | GET | `{ version: str }` → footer version |
| `/api/providers` | GET | `{ providers: [{id, name, configured, requires_api_key}] }` → provider dropdown |
| `/api/models?provider={id}` | GET | `[str]` or `{ models: [str] }` → model dropdowns |
| `/api/converters` | GET | list → converter select |
| `/api/health/ready` | GET | health check on load |
| `/api/jobs` | POST | create job → `{ job_id: str }` |
| `/api/jobs/{id}/events` | GET | SSE stream — event types: `phase_change`, `log`, `job_done` |
| `/api/jobs/{id}/status` | GET | `{ status, pages_completed, pages_retried }` |
| `/api/jobs/{id}/cancel` | POST | cancel running job |
| `/api/jobs/{id}/pause` | POST | pause running job (poll status after, no SSE) |
| `/api/jobs/{id}/resume` | POST | resume paused job (poll status after, no SSE) |
| `/api/jobs/resume-from-state` | POST | `{ state_path: str }` |

**No `GET /api/jobs` list endpoint** — job history lives in a local in-memory array, same as current UI.

**SSE `job_done` payload:** `{ status, pages_ok, pages_partial, pages_failed, pages_retried }`. Use `pages_partial` and `pages_failed` from here (NOT from `/status` polling — those fields are absent from `JobStatus` model).

**Pause/Resume:** No SSE event emitted. After API call, immediately `GET /api/jobs/{id}/status` to read new state.

---

## Chunk 1: HTML Shell + CSS

### Task 1: Create feature branch

**Files:**
- No file changes — git only

- [ ] **Step 1: Create and check out branch**
  ```bash
  rtk git checkout -b ui-redesign
  ```
  Expected: `Switched to a new branch 'ui-redesign'`

---

### Task 2: Write the full HTML + CSS shell

The complete HTML structure and all CSS from mockup v4, adapted for production (no mock/static data, empty containers that JS will populate).

**Files:**
- Modify: `src/ui/index.html` (full rewrite)

- [ ] **Step 1: Open reference mockup to understand structure**

  Read `docs/designs/ui-redesign-mockup-v4.html` — full file. This is the approved visual source of truth.

- [ ] **Step 2: Rewrite `src/ui/index.html` — head + CSS**

  Write the complete `<head>` and `<style>` block. CSS must exactly match spec (Section 3–10 of `docs/superpowers/specs/2026-03-22-ui-redesign-design.md`). Key rules:

  ```html
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docrawl</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
      /* 1. Reset */
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      /* 2. Design tokens */
      :root {
        --bg: #0e0e0e;
        --bg-panel: #111111;
        --bg-input: #181818;
        --bg-raised: #1d1d1d;
        --bg-section: #0f0f0f;
        --border: #252525;
        --border-mid: #333333;
        --border-hi: #444444;
        --text: #e8e8e8;
        --text-dim: #909090;
        --text-muted: #686868;
        --accent: #c87941;
        --accent-dim: #6b3f1e;
        --accent-hover: #d68f55;
        --accent-bg: rgba(200,121,65,0.06);
        --accent-text: rgba(200,121,65,0.80);
        --ok: #5c8f5c;
        --ok-dim: rgba(92,143,92,0.25);
        --warn: #9e8638;
        --warn-dim: rgba(158,134,56,0.25);
        --err: #a05050;
        --err-dim: rgba(160,80,80,0.25);
        --info: #4f7a9a;
        --info-dim: rgba(79,122,154,0.25);
        --font: 'IBM Plex Mono', 'Courier New', monospace;
      }

      /* 3. Layout — full-viewport grid, no overflow */
      html, body {
        height: 100%;
        overflow: hidden;
      }
      body {
        display: grid;
        grid-template-rows: 48px 1fr 30px;
        height: 100vh;
        width: 100vw;
        font-family: var(--font);
        font-size: 13px;
        line-height: 1.5;
        color: var(--text);
        background: var(--bg);
        overflow: hidden;
      }

      /* ... all other CSS from mockup v4, adapted exactly */
    </style>
  </head>
  ```

  **CRITICAL CSS rules to include exactly as specified:**

  - `.left-panel`: `overflow-y: auto; overflow-x: hidden; scrollbar-width: thin;`
  - `.right-panel`: `overflow: hidden; display: flex; flex-direction: column;`
  - `.job-history`: `display: flex; flex-direction: column; flex: 1; overflow: hidden;`
  - `.job-list`: `flex: 1; overflow-y: auto;`
  - `.advanced-content { display: none; }` / `.advanced-content[aria-hidden="false"] { display: block; }`
  - `.tooltip { position: fixed; z-index: 10000; pointer-events: none; }` (body-appended, not `::after`)
  - `.pulse-dot.running { animation: pulse 1s ease-in-out infinite; }`
  - Amber (`--accent`) used ONLY for: `.wordmark-accent`, `.btn-execute`, `.pulse-dot`, `.job-id` (running only), running badge

- [ ] **Step 3: Write HTML body — header**

  The header has named provider indicator divs. JS will populate the dot color + model count for Ollama and LMStudio after `loadProviders()` resolves.

  ```html
  <body>
  <header>
    <div class="header-left">
      <span class="wordmark">DOC<span class="wordmark-accent">RAWL</span></span>
    </div>
    <div class="header-status-indicators">
      <div class="indicator ollama-indicator" id="ind-ollama">
        <span class="indicator-dot" id="dot-ollama"></span>
        <span class="indicator-label" id="label-ollama">Ollama</span>
      </div>
      <div class="indicator lmstudio-indicator" id="ind-lmstudio">
        <span class="indicator-dot" id="dot-lmstudio"></span>
        <span class="indicator-label" id="label-lmstudio">LMStudio</span>
      </div>
      <div class="indicator disk-indicator">
        <span class="indicator-label" id="label-disk">Disk: —</span>
      </div>
      <div class="indicator write-indicator">
        <span class="indicator-label" id="label-write">Write: —</span>
      </div>
    </div>
  </header>
  ```

- [ ] **Step 4: Write HTML body — main + left panel**

  Left panel groups (top to bottom per spec Section 7):
  1. `// TARGET` — URL input (full width, 15px, `type="url"`)
  2. `// LLM` — Provider select (dynamic) + 3-col model grid (Crawl/Pipeline/Reasoning)
  3. `// OUTPUT` — output path (2fr) + format (1fr) in a row, then language (full width)
  4. `// CONTROLS` — EXECUTE button (42px amber) + 3-col row (PAUSE / RESUME / CANCEL, ghost buttons, disabled by default)
  5. `// OPTIONS` — compact 2-col grid with `data-tooltip` on all controls
  6. `// ADVANCED` — collapsible, `aria-expanded="false"` by default

  ```html
  <main class="main">
    <div class="left-panel">
      <!-- Group: Target -->
      <section class="form-group group-target">
        <div class="group-header">// TARGET</div>
        <input type="url" id="crawlUrl" name="url" placeholder="https://..." autocomplete="off" required>
      </section>

      <!-- Group: LLM -->
      <section class="form-group group-llm">
        <div class="group-header">// LLM</div>
        <select id="providerSelect" name="provider">
          <option value="">Loading providers…</option>
        </select>
        <div class="group-llm-grid">
          <div class="field-wrap">
            <label>Crawl Model</label>
            <select id="crawlModel" name="crawl_model"><option value="">—</option></select>
          </div>
          <div class="field-wrap">
            <label>Pipeline Model</label>
            <select id="pipelineModel" name="pipeline_model"><option value="">—</option></select>
          </div>
          <div class="field-wrap">
            <label>Reasoning Model</label>
            <select id="reasoningModel" name="reasoning_model"><option value="">—</option></select>
          </div>
        </div>
      </section>

      <!-- Group: Output -->
      <section class="form-group group-output">
        <div class="group-header">// OUTPUT</div>
        <div class="group-output-row">
          <input type="text" id="outputPath" name="output_path" placeholder="/output/path">
          <select id="outputFormat" name="output_format">
            <option value="markdown">markdown</option>
            <option value="json">json</option>
          </select>
        </div>
        <select id="language" name="language">
          <option value="en">English (en)</option>
          <option value="es">Spanish (es)</option>
          <option value="fr">French (fr)</option>
          <option value="de">German (de)</option>
          <option value="zh">Chinese (zh)</option>
          <option value="ja">Japanese (ja)</option>
          <option value="pt">Portuguese (pt)</option>
          <option value="ru">Russian (ru)</option>
          <option value="ar">Arabic (ar)</option>
          <option value="ko">Korean (ko)</option>
        </select>
      </section>

      <!-- Group: Controls -->
      <section class="form-group group-controls">
        <button class="btn-execute" id="btnExecute" type="button">◆ EXECUTE CRAWL</button>
        <div class="controls-row">
          <button class="btn-ghost btn-pause" id="btnPause" type="button" disabled>PAUSE</button>
          <button class="btn-ghost btn-resume" id="btnResume" type="button" disabled>RESUME</button>
          <button class="btn-ghost btn-cancel" id="btnCancel" type="button" disabled>CANCEL</button>
        </div>
      </section>

      <!-- Group: Options -->
      <!-- NOTE: .options-2col is grid-template-columns: 1fr 1fr per spec — DO NOT change to 3-col.
           Three number inputs in a 2-col grid means Max Depth wraps to row 2 (left-aligned).
           This matches the spec diagram intentionally. -->
      <section class="form-group group-options">
        <div class="group-header">// OPTIONS</div>
        <div class="options-2col">
          <div class="field-wrap">
            <label data-tooltip="Delay between requests in milliseconds. Min 100, max 60000.">
              Request Delay (ms)
            </label>
            <input type="number" id="delayMs" name="delay_ms" value="1000" min="100" max="60000" step="100" data-tooltip="Delay between requests in milliseconds. Min 100, max 60000.">
          </div>
          <div class="field-wrap">
            <label data-tooltip="Maximum concurrent HTTP requests. Min 1, max 10.">
              Max Concurrent
            </label>
            <input type="number" id="maxConcurrent" name="max_concurrent" value="5" min="1" max="10" data-tooltip="Maximum concurrent HTTP requests. Min 1, max 10.">
          </div>
          <div class="field-wrap">
            <label data-tooltip="Maximum crawl depth from the start URL. Min 1, max 20.">
              Max Depth
            </label>
            <input type="number" id="maxDepth" name="max_depth" value="10" min="1" max="20" data-tooltip="Maximum crawl depth from the start URL. Min 1, max 20.">
          </div>
        </div>
        <label class="checkbox-row" data-tooltip="Honor robots.txt exclusion rules.">
          <input type="checkbox" id="respectRobots" name="respect_robots_txt" checked> Respect robots.txt
        </label>
        <label class="checkbox-row" data-tooltip="Only crawl pages under the same path as the start URL.">
          <input type="checkbox" id="filterSitemap" name="filter_sitemap_by_path" checked> Filter sitemap by path
        </label>
        <label class="checkbox-row" data-tooltip="Use lightweight HTTP requests to quickly probe pages.">
          <input type="checkbox" id="httpFastPath" name="http_fast_path"> HTTP Fast-Path
        </label>
        <label class="checkbox-row" data-tooltip="Cache pages for 24 hours to skip re-fetching unchanged content.">
          <input type="checkbox" id="useCache" name="use_cache" checked> Cache (24h)
        </label>
        <label class="checkbox-row" data-tooltip="Fetch and clean up pages in parallel for faster throughput.">
          <input type="checkbox" id="pipelineMode" name="pipeline_mode"> Pipeline Mode
        </label>
        <label class="checkbox-row" data-tooltip="Use browser native Markdown rendering instead of conversion.">
          <input type="checkbox" id="nativeMarkdown" name="native_markdown"> Native Markdown
        </label>
        <div class="field-wrap">
          <label>Converter</label>
          <select id="converter" name="converter" class="converter-select">
            <option value="markdownify">markdownify</option>
            <!-- JS populates from GET /api/converters -->
          </select>
        </div>
      </section>

      <!-- Group: Advanced (collapsible) -->
      <section class="form-group group-advanced">
        <button class="advanced-toggle" aria-expanded="false" type="button">ADVANCED OPTIONS</button>
        <div class="advanced-content" aria-hidden="true">
          <label class="checkbox-row" data-tooltip="Skip the LLM post-processing cleanup step.">
            <input type="checkbox" id="skipLlmCleanup" name="skip_llm_cleanup"> Skip LLM Cleanup
          </label>
          <label class="checkbox-row" data-tooltip="Proxy markdown conversion through an external URL.">
            <input type="checkbox" id="markdownProxy" name="use_markdown_proxy"> Markdown Proxy
          </label>
          <div class="markdown-proxy-url-wrapper" style="display:none;">
            <input type="url" id="markdownProxyUrl" name="markdown_proxy_url"
              placeholder="https://proxy.example.com"
              data-tooltip="URL of the markdown proxy service.">
          </div>

          <div class="chip-field">
            <label>Content Selectors <span class="chip-count">(max 20)</span></label>
            <div class="chip-input-container" id="contentSelectorsContainer">
              <input type="text" class="chip-input" id="contentSelectorsInput"
                placeholder="Enter CSS selector, press Enter"
                data-chip-target="contentSelectorsContainer"
                data-max="20">
            </div>
          </div>

          <div class="chip-field">
            <label>Noise Selectors <span class="chip-count">(max 20)</span></label>
            <div class="chip-input-container" id="noiseSelectorContainer">
              <input type="text" class="chip-input" id="noiseSelectorInput"
                placeholder="Enter CSS selector, press Enter"
                data-chip-target="noiseSelectorContainer"
                data-max="20">
            </div>
          </div>

          <div class="field-wrap resume-state-wrap">
            <label>Resume from State</label>
            <input type="text" id="resumeStatePath" name="resume_state_path"
              placeholder="/path/to/.job_state.json">
            <button class="btn-ghost btn-resume-state" id="btnResumeState" type="button" disabled>
              RESUME
            </button>
          </div>
        </div>
      </section>
    </div>

    <div class="divider"></div>

    <!-- Right Panel -->
    <div class="right-panel">
      <!-- Active crawl strip -->
      <div class="active-status" id="activeStatus">
        <span class="pulse-dot" id="pulseDot"></span>
        <span class="current-url" id="currentUrl"></span>
        <span class="idle-text" id="idleText">Idle</span>
      </div>

      <!-- Mission Report 2x2 -->
      <div class="mission-report">
        <div class="metric-card">
          <div class="metric-number" id="stat-complete">0</div>
          <div class="metric-label">COMPLETE</div>
        </div>
        <div class="metric-card">
          <div class="metric-number" id="stat-partial">0</div>
          <div class="metric-label">PARTIAL</div>
        </div>
        <div class="metric-card">
          <div class="metric-number" id="stat-failed">0</div>
          <div class="metric-label">FAILED</div>
        </div>
        <div class="metric-card">
          <div class="metric-number" id="stat-retried">0</div>
          <div class="metric-label">RETRIED</div>
        </div>
      </div>

      <!-- Job History -->
      <div class="job-history">
        <input type="search" class="job-history-filter" id="jobHistoryFilter"
          placeholder="Search job ID or URL…" autocomplete="off">
        <div class="job-list" id="jobList">
          <div class="job-empty">No jobs yet</div>
        </div>
      </div>
    </div>
  </main>
  ```

- [ ] **Step 5: Write HTML body — footer**

  ```html
  <footer>
    <div class="footer-version">
      <span id="footerVersion">v—</span>
      <span>•</span>
      <a href="https://github.com/plateeater/docrawl" target="_blank" rel="noopener">GitHub</a>
    </div>
    <div class="footer-models" id="footerModels"></div>
  </footer>
  </body>
  </html>
  ```

- [ ] **Step 6: Verify layout renders (static — no JS yet)**

  Start server:
  ```bash
  cd C:/xcode/docrawl && .venv/scripts/uvicorn.exe src.api.main:app --host 0.0.0.0 --port 8002 --reload &
  ```
  Then verify:
  ```bash
  PYTHONUTF8=1 .venv/scripts/browser-use.exe open http://localhost:8002
  PYTHONUTF8=1 .venv/scripts/browser-use.exe screenshot
  ```
  **Expected:** Full-viewport layout, no scroll. Header 48px with DOCRAWL wordmark. Two panels 50/50. Footer 30px. No old theme colors. Amber on RAWL only.

- [ ] **Step 7: Commit static shell**

  ```bash
  rtk git add src/ui/index.html
  rtk git commit -m "feat(ui): rewrite static HTML shell + CSS — industrial theme"
  ```

---

## Chunk 2: JavaScript

### Task 3: Write initialization JS (page load)

**Files:**
- Modify: `src/ui/index.html` — add `<script>` block

- [ ] **Step 1: Write `<script>` block skeleton + constants**

  ```javascript
  <script>
  'use strict';

  const MAX_JOB_HISTORY = 50;
  const jobHistory = [];
  let currentJobId = null;
  let eventSource = null;

  // ─── DOM refs ─────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const crawlUrl       = $('crawlUrl');
  const providerSelect = $('providerSelect');
  const crawlModel     = $('crawlModel');
  const pipelineModel  = $('pipelineModel');
  const reasoningModel = $('reasoningModel');
  const outputPath     = $('outputPath');
  const outputFormat   = $('outputFormat');
  const language       = $('language');
  const btnExecute     = $('btnExecute');
  const btnPause       = $('btnPause');
  const btnResume      = $('btnResume');
  const btnCancel      = $('btnCancel');
  const btnResumeState = $('btnResumeState');
  const pulseDot       = $('pulseDot');
  const currentUrl     = $('currentUrl');
  const idleText       = $('idleText');
  const jobList        = $('jobList');
  const jobHistoryFilter = $('jobHistoryFilter');
  const resumeStatePath  = $('resumeStatePath');
  ```

- [ ] **Step 2: Write `loadInfo()` — fetch version from `GET /api/info`**

  ```javascript
  async function loadInfo() {
    try {
      const info = await fetch('/api/info').then(r => r.json());
      $('footerVersion').textContent = `v${info.version}`;
    } catch (e) {
      console.warn('GET /api/info failed', e);
    }
  }
  ```

- [ ] **Step 3: Write `loadProviders()` — fetch `GET /api/providers`, populate dropdown + header dots**

  After populating the select, call `updateProviderIndicators(providers)` to color the Ollama/LMStudio header dots.

  ```javascript
  async function loadProviders() {
    try {
      const data = await fetch('/api/providers').then(r => r.json());
      const providers = data.providers || [];
      providerSelect.innerHTML = providers.map(p =>
        `<option value="${p.id}" ${!p.configured ? 'class="unconfigured"' : ''}>${p.name}${!p.configured ? ' (not configured)' : ''}</option>`
      ).join('');
      updateProviderIndicators(providers);
      if (providers.length > 0) {
        await loadModels(providers[0].id);
      }
    } catch (e) {
      console.warn('GET /api/providers failed — using fallback', e);
      providerSelect.innerHTML = `
        <option value="ollama">Ollama</option>
        <option value="lmstudio">LMStudio</option>
        <option value="openrouter">OpenRouter</option>
        <option value="opencode">OpenCode</option>
        <option value="llamacpp">llama.cpp</option>
      `;
    }
  }

  function updateProviderIndicators(providers) {
    // Color Ollama and LMStudio header dots: online (--ok) if configured, offline (--err) if not
    const find = id => providers.find(p => p.id === id);
    const updateIndicator = (dotId, labelId, providerId, name) => {
      const dot = $(dotId);
      const label = $(labelId);
      if (!dot || !label) return;
      const p = find(providerId);
      dot.classList.toggle('offline', !p || !p.configured);
      label.textContent = name; // model count appended separately in updateIndicatorModelCount()
    };
    updateIndicator('dot-ollama',   'label-ollama',   'ollama',   'Ollama');
    updateIndicator('dot-lmstudio', 'label-lmstudio', 'lmstudio', 'LMStudio');
  }

  function updateIndicatorModelCount(providerId, modelCount) {
    // Spec Section 6: model count appended to indicator label, e.g. "Ollama (3 models)"
    const labelMap = { ollama: 'label-ollama', lmstudio: 'label-lmstudio' };
    const nameMap  = { ollama: 'Ollama',       lmstudio: 'LMStudio' };
    const labelId = labelMap[providerId];
    if (!labelId) return;
    const label = $(labelId);
    if (!label) return;
    const name = nameMap[providerId];
    label.textContent = modelCount > 0 ? `${name} (${modelCount} models)` : name;
  }
  ```

- [ ] **Step 4: Write `loadModels(provider)` — fetch `GET /api/models?provider={id}`**

  ```javascript
  async function loadModels(provider) {
    const placeholder = '<option value="">—</option>';
    [crawlModel, pipelineModel, reasoningModel].forEach(s => s.innerHTML = placeholder);
    if (!provider) return;
    try {
      const data = await fetch(`/api/models?provider=${encodeURIComponent(provider)}`).then(r => r.json());
      const models = Array.isArray(data) ? data : (data.models || []);
      const options = placeholder + models.map(m => `<option value="${m}">${m}</option>`).join('');
      [crawlModel, pipelineModel, reasoningModel].forEach(s => s.innerHTML = options);
      // Update header indicator model count for Ollama/LMStudio (spec Section 6)
      updateIndicatorModelCount(provider, models.length);
    } catch (e) {
      console.warn('GET /api/models failed', e);
    }
  }

  providerSelect.addEventListener('change', () => loadModels(providerSelect.value));
  ```

- [ ] **Step 5: Write `loadConverters()` — fetch `GET /api/converters`**

  ```javascript
  async function loadConverters() {
    try {
      const data = await fetch('/api/converters').then(r => r.json());
      const converters = Array.isArray(data) ? data : (data.converters || []);
      const sel = $('converter');
      sel.innerHTML = converters.map(c => `<option value="${c}">${c}</option>`).join('');
    } catch (e) {
      console.warn('GET /api/converters failed', e);
    }
  }
  ```

- [ ] **Step 6: Write `DOMContentLoaded` init block**

  ```javascript
  document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([loadInfo(), loadProviders(), loadConverters()]);
    initTooltips();
    initChipInputs();
    initAdvancedToggle();
    initMarkdownProxyToggle();
    initResumeStateButton();
    initJobHistoryFilter();
    renderJobList();
  });
  ```

- [ ] **Step 7: Verify init**

  ```bash
  PYTHONUTF8=1 .venv/scripts/browser-use.exe open http://localhost:8002
  PYTHONUTF8=1 .venv/scripts/browser-use.exe screenshot
  ```
  **Expected:** Provider dropdown populated from API (or fallback). Model dropdowns populated. Converter dropdown populated. Footer shows version from `GET /api/info`.

- [ ] **Step 8: Commit init JS**

  ```bash
  rtk git add src/ui/index.html
  rtk git commit -m "feat(ui): add page-load initialization — providers, models, converters, version"
  ```

---

### Task 4: Write job execution + SSE JS

**Files:**
- Modify: `src/ui/index.html` — append to `<script>` block

- [ ] **Step 1: Write `collectFormData()` — assemble `POST /api/jobs` body**

  ```javascript
  function collectFormData() {
    const getChips = containerId => {
      return Array.from(document.querySelectorAll(`#${containerId} .chip`))
        .map(c => c.dataset.value)
        .filter(Boolean);
    };

    const body = {
      url:                    crawlUrl.value.trim(),
      provider:               providerSelect.value,
      crawl_model:            crawlModel.value || undefined,
      pipeline_model:         pipelineModel.value || undefined,
      reasoning_model:        reasoningModel.value || undefined,
      output_path:            outputPath.value.trim() || undefined,
      output_format:          outputFormat.value || 'markdown',
      language:               language.value || 'en',
      delay_ms:               parseInt($('delayMs').value) || 1000,
      max_concurrent:         parseInt($('maxConcurrent').value) || 5,
      max_depth:              parseInt($('maxDepth').value) || 10,
      respect_robots_txt:     $('respectRobots').checked,
      filter_sitemap_by_path: $('filterSitemap').checked,
      http_fast_path:         $('httpFastPath').checked,
      use_cache:              $('useCache').checked,
      pipeline_mode:          $('pipelineMode').checked,
      native_markdown:        $('nativeMarkdown').checked,
      converter:              $('converter').value || 'markdownify',
      skip_llm_cleanup:       $('skipLlmCleanup').checked,
      use_markdown_proxy:     $('markdownProxy').checked,
      markdown_proxy_url:     $('markdownProxy').checked ? $('markdownProxyUrl').value.trim() : undefined,
      content_selectors:      getChips('contentSelectorsContainer'),
      noise_selectors:        getChips('noiseSelectorContainer'),
    };

    // Remove undefined fields
    Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
    return body;
  }
  ```

- [ ] **Step 2: Write `startJob()` — POST + open SSE stream**

  ```javascript
  async function startJob() {
    if (!crawlUrl.value.trim()) {
      crawlUrl.focus();
      return;
    }

    setExecuteState('running');
    resetMissionReport();

    let jobId;
    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collectFormData()),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      jobId = data.job_id;
    } catch (e) {
      console.error('POST /api/jobs failed', e);
      setExecuteState('idle');
      return;
    }

    currentJobId = jobId;
    addJobToHistory({ id: jobId, status: 'running', url: crawlUrl.value.trim(), ts: Date.now() });
    openEventSource(jobId);
  }

  btnExecute.addEventListener('click', startJob);
  ```

- [ ] **Step 3: Write `openEventSource(jobId)` — SSE handler**

  ```javascript
  function openEventSource(jobId) {
    if (eventSource) { eventSource.close(); eventSource = null; }

    eventSource = new EventSource(`/api/jobs/${jobId}/events`);

    eventSource.addEventListener('phase_change', e => {
      const data = JSON.parse(e.data);
      if (data.current_url) {
        setActiveUrl(data.current_url);
      }
      if (typeof data.pages_completed === 'number') {
        $('stat-complete').textContent = data.pages_completed;
      }
      if (typeof data.pages_retried === 'number') {
        $('stat-retried').textContent = data.pages_retried;
      }
    });

    eventSource.addEventListener('job_done', e => {
      const data = JSON.parse(e.data);
      updateMissionReport(data);
      updateControlButtons(data.status);
      setActiveIdle();
      updateJobInHistory(jobId, data.status);
      updateFooterModels();
      eventSource.close();
      eventSource = null;
      currentJobId = null;
    });

    eventSource.onerror = () => {
      eventSource.close();
      eventSource = null;
      updateControlButtons('failed');
      setActiveIdle();
    };

    setActiveUrl('Connecting…');
    updateControlButtons('running');
  }
  ```

- [ ] **Step 4: Write `updateMissionReport(data)` — from `job_done` SSE payload**

  ```javascript
  function updateMissionReport(data) {
    // pages_partial and pages_failed come ONLY from job_done SSE payload
    // (absent from JobStatus model / GET /status response)
    $('stat-complete').textContent = data.pages_ok       ?? 0;
    $('stat-partial').textContent  = data.pages_partial  ?? 0;
    $('stat-failed').textContent   = data.pages_failed   ?? 0;
    $('stat-retried').textContent  = data.pages_retried  ?? 0;
  }

  function resetMissionReport() {
    ['stat-complete','stat-partial','stat-failed','stat-retried']
      .forEach(id => $(id).textContent = '0');
  }
  ```

- [ ] **Step 5: Write active status helpers**

  ```javascript
  function setActiveUrl(url) {
    pulseDot.classList.add('running');
    currentUrl.textContent = url;
    currentUrl.style.display = '';
    idleText.style.display = 'none';
  }

  function setActiveIdle() {
    pulseDot.classList.remove('running');
    currentUrl.textContent = '';
    currentUrl.style.display = 'none';
    idleText.style.display = '';
  }

  function setExecuteState(state) {
    if (state === 'running') {
      btnExecute.disabled = true;
    } else {
      btnExecute.disabled = false;
    }
  }
  ```

- [ ] **Step 6: Verify job execution**

  With Docrawl server running, submit a test crawl in the browser:
  ```bash
  PYTHONUTF8=1 .venv/scripts/browser-use.exe open http://localhost:8002
  PYTHONUTF8=1 .venv/scripts/browser-use.exe state
  ```
  Fill in URL field and click EXECUTE CRAWL. Verify:
  - Pulse dot appears, current_url updates
  - PAUSE/CANCEL buttons enable
  - Mission report numbers update after job_done
  - Job appears in history list

- [ ] **Step 7: Commit execution JS**

  ```bash
  rtk git add src/ui/index.html
  rtk git commit -m "feat(ui): add job execution — POST /jobs, SSE events, mission report"
  ```

---

### Task 5: Write controls + advanced JS

**Files:**
- Modify: `src/ui/index.html` — append to `<script>` block

- [ ] **Step 1: Write `updateControlButtons(status)` — manage button enabled/disabled state**

  ```javascript
  function updateControlButtons(status) {
    const isRunning  = status === 'running';
    const isPaused   = status === 'paused';
    const isActive   = isRunning || isPaused;

    btnPause.disabled  = !isRunning;
    btnResume.disabled = !isPaused;
    btnCancel.disabled = !isActive;
    btnExecute.disabled = isActive;
  }
  ```

- [ ] **Step 2: Write pause/resume/cancel — with polling**

  ```javascript
  async function pollStatus(jobId) {
    try {
      const s = await fetch(`/api/jobs/${jobId}/status`).then(r => r.json());
      updateControlButtons(s.status);
      if (s.status === 'paused') {
        setActiveUrl('Paused');
      }
    } catch (e) {
      console.warn('GET /api/jobs/status failed', e);
    }
  }

  btnPause.addEventListener('click', async () => {
    if (!currentJobId) return;
    await fetch(`/api/jobs/${currentJobId}/pause`, { method: 'POST' });
    await pollStatus(currentJobId);
  });

  btnResume.addEventListener('click', async () => {
    if (!currentJobId) return;
    await fetch(`/api/jobs/${currentJobId}/resume`, { method: 'POST' });
    await pollStatus(currentJobId);
    if (eventSource === null && currentJobId) {
      openEventSource(currentJobId);
    }
  });

  btnCancel.addEventListener('click', async () => {
    if (!currentJobId) return;
    await fetch(`/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
    updateControlButtons('cancelled');
    setActiveIdle();
    updateJobInHistory(currentJobId, 'cancelled');
    if (eventSource) { eventSource.close(); eventSource = null; }
    currentJobId = null;
  });
  ```

- [ ] **Step 3: Write job history helpers**

  ```javascript
  function addJobToHistory(job) {
    jobHistory.unshift(job);
    if (jobHistory.length > MAX_JOB_HISTORY) jobHistory.pop();
    renderJobList();
  }

  function updateJobInHistory(jobId, status) {
    const job = jobHistory.find(j => j.id === jobId);
    if (job) { job.status = status; renderJobList(); }
  }

  function renderJobList() {
    const q = jobHistoryFilter.value.trim().toLowerCase();
    const filtered = q
      ? jobHistory.filter(j => j.id.includes(q) || (j.url || '').toLowerCase().includes(q))
      : jobHistory;

    if (filtered.length === 0) {
      jobList.innerHTML = '<div class="job-empty">No jobs yet</div>';
      return;
    }

    // NOTE: .job-id is ALWAYS amber per spec CSS (color: var(--accent)).
    // The 'running' class on the id span adds the pulse animation only; it does not change the color.
    // All job IDs render amber regardless of status — this is correct per spec.
    //
    // NOTE: .job-status-badge is a CSS-styled 8×8px colored circle (border-radius: 50%).
    // Render it as an EMPTY <span> — color comes from CSS class, NOT from text content.
    // Do NOT put text characters (●, ✓, etc.) inside the badge span — they conflict with the
    // fixed 8px box size and break the layout.
    jobList.innerHTML = filtered.map(j => {
      const idClass = j.status === 'running' ? 'job-id running' : 'job-id';
      const dotClass = { running: 'running', completed: 'complete', failed: 'failed', cancelled: 'failed', paused: 'partial' }[j.status] || '';
      const ts = j.ts ? new Date(j.ts).toLocaleTimeString() : '';
      return `
        <div class="job-item" data-id="${j.id}">
          <span class="${idClass}">#${j.id.slice(0,8)}</span>
          <span class="job-status-badge ${dotClass}" title="${j.status}"></span>
          <span class="job-url" title="${j.url || ''}">${j.url || '—'}</span>
          <span class="job-timestamp">${ts}</span>
        </div>`;
    }).join('');
  }

  function initJobHistoryFilter() {
    jobHistoryFilter.addEventListener('input', renderJobList);
  }
  ```

- [ ] **Step 4: Write advanced section toggle**

  ```javascript
  function initAdvancedToggle() {
    const toggle = document.querySelector('.advanced-toggle');
    const content = document.querySelector('.advanced-content');
    toggle.addEventListener('click', () => {
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      content.setAttribute('aria-hidden', String(expanded));
    });
  }
  ```

- [ ] **Step 5: Write markdown proxy URL reveal**

  ```javascript
  function initMarkdownProxyToggle() {
    const cb = $('markdownProxy');
    const wrapper = document.querySelector('.markdown-proxy-url-wrapper');
    cb.addEventListener('change', () => {
      wrapper.style.display = cb.checked ? 'block' : 'none';
    });
  }
  ```

- [ ] **Step 6: Write chip input manager**

  ```javascript
  function addChip(container, value) {
    const input = container.querySelector('.chip-input');
    const max = parseInt(input.dataset.max) || 20;
    const chips = container.querySelectorAll('.chip');
    if (chips.length >= max) return;

    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.dataset.value = value;
    chip.innerHTML = `${value} <span class="chip-remove" role="button" aria-label="Remove">×</span>`;
    chip.querySelector('.chip-remove').addEventListener('click', () => chip.remove());
    container.insertBefore(chip, input);
  }

  function initChipInputs() {
    document.querySelectorAll('.chip-input').forEach(input => {
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const val = input.value.trim();
          if (val) {
            const container = input.closest('.chip-input-container');
            const max = parseInt(input.dataset.max) || 20;
            if (container.querySelectorAll('.chip').length < max) {
              addChip(container, val);
              input.value = '';
            }
          }
        } else if (e.key === 'Escape') {
          input.value = '';
        }
      });
    });
  }
  ```

- [ ] **Step 7: Write resume-from-state button**

  ```javascript
  function initResumeStateButton() {
    resumeStatePath.addEventListener('input', () => {
      btnResumeState.disabled = !resumeStatePath.value.trim();
    });

    btnResumeState.addEventListener('click', async () => {
      const path = resumeStatePath.value.trim();
      if (!path) return;
      try {
        const res = await fetch('/api/jobs/resume-from-state', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state_path: path }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const jobId = data.job_id;
        currentJobId = jobId;
        addJobToHistory({ id: jobId, status: 'running', url: path, ts: Date.now() });
        openEventSource(jobId);
      } catch (e) {
        console.error('POST /api/jobs/resume-from-state failed', e);
      }
    });
  }
  ```

- [ ] **Step 8: Write tooltip handler (body-appended, not CSS ::after)**

  The tooltip MUST be appended to `document.body` and use `position: fixed`. CSS `::after` does NOT work because parent panels have `overflow: hidden`.

  ```javascript
  function initTooltips() {
    let activeTooltip = null;

    document.addEventListener('mouseenter', e => {
      const target = e.target.closest('[data-tooltip]');
      if (!target) return;

      if (activeTooltip) { activeTooltip.remove(); activeTooltip = null; }

      const tt = document.createElement('div');
      tt.className = 'tooltip';
      tt.textContent = target.dataset.tooltip;
      document.body.appendChild(tt);
      activeTooltip = tt;

      const rect = target.getBoundingClientRect();
      const ttRect = tt.getBoundingClientRect();
      let left = rect.left + rect.width / 2 - ttRect.width / 2;
      let top  = rect.top - ttRect.height - 6;

      // Clamp to viewport
      left = Math.max(4, Math.min(left, window.innerWidth - ttRect.width - 4));
      if (top < 4) top = rect.bottom + 6;

      tt.style.left = left + 'px';
      tt.style.top  = top + 'px';

      let autoHideTimer;
      const hide = () => {
        clearTimeout(autoHideTimer);
        tt.remove();
        if (activeTooltip === tt) activeTooltip = null;
        target.removeEventListener('mouseleave', hide);
      };
      target.addEventListener('mouseleave', hide);
      // Auto-hide after 5 seconds of inactivity (per spec Section 10)
      autoHideTimer = setTimeout(hide, 5000);
    }, true);
  }
  ```

- [ ] **Step 9: Write `updateFooterModels()` — show models used**

  ```javascript
  function updateFooterModels() {
    const models = [crawlModel, pipelineModel, reasoningModel]
      .map(s => s.value).filter(Boolean);
    const unique = [...new Set(models)];
    $('footerModels').textContent = unique.length
      ? `Models: ${unique.join(', ')}`
      : '';
  }
  ```

- [ ] **Step 10: Final browser-use verification**

  ```bash
  PYTHONUTF8=1 .venv/scripts/browser-use.exe open http://localhost:8002
  PYTHONUTF8=1 .venv/scripts/browser-use.exe screenshot
  ```

  Verify each feature:
  1. Page loads, no scroll, layout fills viewport
  2. DOCRAWL wordmark in header, amber on RAWL only
  3. Provider dropdown populated from API
  4. Expand Advanced section — all fields visible, no content cut off by footer
  5. Hover over a field with `data-tooltip` — tooltip appears correctly positioned
  6. Type a CSS selector in Content Selectors, press Enter — chip appears
  7. Click chip × — chip removed
  8. Check Markdown Proxy — URL field appears

  If any issue is found: fix before committing.

- [ ] **Step 11: Commit JS**

  ```bash
  rtk git add src/ui/index.html
  rtk git commit -m "feat(ui): add controls, advanced panel, chips, tooltips, job history"
  ```

---

## Chunk 3: PR + Cleanup

### Task 6: Pre-push cleanup

**Files:**
- Modify: `.gitignore` (if needed)

- [ ] **Step 1: Check for temp files in working tree**

  ```bash
  rtk git status
  ```
  Look for any leftover temp/scratch files (e.g., mockup iterations in root dir).

- [ ] **Step 2: Verify nothing sensitive is staged**

  Confirm only `src/ui/index.html` changed (plus any cleanup). No `.env`, no test artifacts.

- [ ] **Step 3: Ensure `docs/designs/ui-redesign-mockup-v4.html` and spec are committed**

  ```bash
  rtk git status
  ```
  If the mockup or spec appear as untracked/modified, commit them:
  ```bash
  rtk git add docs/designs/ui-redesign-mockup-v4.html
  rtk git add docs/superpowers/specs/2026-03-22-ui-redesign-design.md
  rtk git add docs/superpowers/plans/2026-03-22-ui-redesign.md
  rtk git commit -m "docs: add UI redesign spec, mockup v4, and implementation plan"
  ```

---

### Task 7: Open GitHub PR

- [ ] **Step 1: Push branch**

  ```bash
  rtk git push -u origin ui-redesign
  ```

- [ ] **Step 2: Open PR**

  ```bash
  gh pr create \
    --title "feat(ui): redesign — single industrial theme, full API coverage, no scroll" \
    --body "$(cat <<'EOF'
  ## Summary

  Full rewrite of `src/ui/index.html`:

  - **Single dark industrial theme** — eliminates all 4 legacy themes (SYNTHWAVE/BASIC/TERMINAL/GLASSMORPHISM) and the theme selector
  - **No-scroll layout** — CSS Grid `48px header / 1fr main / 30px footer`, 100vh, left panel scrolls internally
  - **50/50 symmetric panels** — left=config form, right=activity monitor
  - **Full API coverage** — exposes 7 previously missing features: Markdown Proxy URL, Skip LLM Cleanup, Content/Noise Selectors (chip inputs), Pause/Resume buttons, Resume from State, Current URL display, pages_retried in Mission Report
  - **Removes `use_page_pool`** — orphaned field, tracked in issue #201
  - **Body-appended tooltips** — fixes overflow:hidden clipping (CSS ::after was invisible)

  ## Design

  Spec: `docs/superpowers/specs/2026-03-22-ui-redesign-design.md`
  Mockup: `docs/designs/ui-redesign-mockup-v4.html`

  ## Test plan

  - [ ] Page loads at 1920×1080, no scroll bar visible, layout fills viewport
  - [ ] DOCRAWL wordmark renders correctly, amber on RAWL only
  - [ ] Provider/model/converter dropdowns populated from API
  - [ ] Footer shows version from `GET /api/info`
  - [ ] EXECUTE CRAWL → job starts, pulse dot animates, current_url updates
  - [ ] Mission Report updates on `job_done` SSE event
  - [ ] PAUSE → polls `/status` → RESUME button enables
  - [ ] RESUME → polls `/status` → SSE reconnects
  - [ ] CANCEL → job cancelled, buttons reset
  - [ ] Chip inputs: Enter adds chip, × removes chip, max 20 enforced
  - [ ] Markdown Proxy checkbox reveals URL input
  - [ ] Advanced section toggles open/close, all content visible (Resume from State not cut off)
  - [ ] Tooltips appear on hover, positioned correctly, no clipping
  - [ ] Job history filter works

  🤖 Generated with [Claude Code](https://claude.ai/claude-code)
  EOF
  )"
  ```

- [ ] **Step 3: Return PR URL to user**

---

## Notes for the implementing agent

1. **Read the mockup first** (`docs/designs/ui-redesign-mockup-v4.html`) — it's the approved visual blueprint. Port its CSS and HTML structure directly; don't reinvent the design.

2. **Tooltip critical rule:** Use JS body-appended `<div>` with `position: fixed`. Do NOT use CSS `::after` — parent panels have `overflow: hidden` which clips pseudo-elements.

3. **Amber constraint:** `--accent` (#c87941) used ONLY for: RAWL wordmark, EXECUTE button, pulse dot, running badge, active (running) job ID in history list. Everything else uses `--text` or `--text-dim`.

4. **`pages_partial` and `pages_failed`** come from the `job_done` SSE event payload only. They are NOT in `JobStatus` / `GET /status` response. Use them in `updateMissionReport()`.

5. **Pause/Resume** have no corresponding SSE event. Always `GET /api/jobs/{id}/status` immediately after the API call to get updated state.

6. **No `GET /api/jobs` endpoint** — job history is client-side in-memory array only.

7. **Server must bind to `0.0.0.0`** (not localhost). When starting uvicorn: `--host 0.0.0.0`.

8. **Browser-use path:** `C:/xcode/docrawl/.venv/scripts/browser-use.exe`. Always prefix with `PYTHONUTF8=1`.
