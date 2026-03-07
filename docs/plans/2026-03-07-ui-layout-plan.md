# UI Layout Improvement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 1920×1080 layout of `src/ui/index.html` — wider container, 65/35 sticky grid, Execute button moved up, duplicate button removed.

**Architecture:** Single file edit (`src/ui/index.html`). CSS changes in the `<style>` block, HTML changes to form structure, JS cleanup of removed element references. No new files, no new dependencies.

**Tech Stack:** Vanilla HTML/CSS/JS. Playwright (Python 3.11.9 via pyenv) for visual verification.

---

## Task 1: Container width

**Files:**
- Modify: `src/ui/index.html:77`

**Step 1: Apply the change**

Find line 77:
```html
            max-width: 1200px;
```
Replace with:
```html
            max-width: min(1600px, calc(100vw - 48px));
```

**Step 2: Verify with Playwright**

```python
# save as ui-experiments/verify_t1.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')
    width = page.evaluate('document.querySelector(".container").offsetWidth')
    assert width == 1600, f"Expected 1600, got {width}"
    page.screenshot(path=str(OUT / "t1-container-1600.png"))
    # also verify 1440 degrades correctly
    page.set_viewport_size({'width': 1440, 'height': 900})
    width = page.evaluate('document.querySelector(".container").offsetWidth')
    assert width <= 1392, f"Expected <=1392 at 1440vw, got {width}"  # 1440 - 48
    browser.close()
    print("Task 1 OK")
```

Run: `python ui-experiments/verify_t1.py`
Expected: `Task 1 OK`

**Step 3: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): widen container to min(1600px, 100vw-48px) for 1920x1080"
```

---

## Task 2: Grid — 65/35 split with sticky right column

**Files:**
- Modify: `src/ui/index.html:84-103`

**Step 1: Update `.two-columns`**

Find lines 84–90 (`.two-columns` rule):
```css
        .two-columns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            align-items: start;
        }
```
Replace with:
```css
        .two-columns {
            display: grid;
            grid-template-columns: 65% 35%;
            gap: 32px;
            align-items: start;
        }
```

**Step 2: Update `.right-column`**

Find lines 98–103 (`.right-column` rule):
```css
        .right-column {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }
```
Replace with:
```css
        .right-column {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            position: sticky;
            top: 16px;
            max-height: calc(100vh - 80px);
            overflow-y: auto;
        }
```

**Step 3: Verify with Playwright**

```python
# save as ui-experiments/verify_t2.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')
    info = page.evaluate('''() => {
        const left = document.querySelector(".left-column");
        const right = document.querySelector(".right-column");
        const rightStyle = window.getComputedStyle(right);
        return {
            leftWidth: left.offsetWidth,
            rightWidth: right.offsetWidth,
            rightPosition: rightStyle.position,
            rightMaxHeight: rightStyle.maxHeight,
        }
    }''')
    print("Layout info:", info)
    assert info['rightPosition'] == 'sticky', f"Expected sticky, got {info['rightPosition']}"
    # 65/35 of 1600px = 1040/560, minus gap; allow +-20px
    assert 1000 <= info['leftWidth'] <= 1080, f"Left width unexpected: {info['leftWidth']}"
    assert 520 <= info['rightWidth'] <= 600, f"Right width unexpected: {info['rightWidth']}"
    page.screenshot(path=str(OUT / "t2-grid-65-35.png"))
    browser.close()
    print("Task 2 OK")
```

Run: `python ui-experiments/verify_t2.py`
Expected: `Task 2 OK`

**Step 4: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): 65/35 grid split, sticky right column with max-height"
```

---

## Task 3: Breakpoint at 1100px

**Files:**
- Modify: `src/ui/index.html:202` (before the existing `@media (max-width: 900px)`)

**Step 1: Add the new breakpoint**

Find line 202 (`@media (max-width: 900px) {`). Insert **before** it:
```css
        /* Wide layout reverts to single column below 1100px */
        @media (max-width: 1100px) {
            .two-columns { grid-template-columns: 1fr; }
            .right-column { position: static; max-height: none; overflow-y: visible; }
        }

```

**Step 2: Verify with Playwright**

```python
# save as ui-experiments/verify_t3.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()

    # At 1099px — should be single column
    page = browser.new_page(viewport={'width': 1099, 'height': 800})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')
    cols = page.evaluate('''() => window.getComputedStyle(document.querySelector(".two-columns")).gridTemplateColumns''')
    pos  = page.evaluate('''() => window.getComputedStyle(document.querySelector(".right-column")).position''')
    assert '1fr' in cols or cols.count('px') == 1, f"Expected single col, got: {cols}"
    assert pos == 'static', f"Expected static, got: {pos}"
    page.close()

    # At 1200px — should still be two columns
    page = browser.new_page(viewport={'width': 1200, 'height': 800})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')
    cols = page.evaluate('''() => window.getComputedStyle(document.querySelector(".two-columns")).gridTemplateColumns''')
    assert cols.count('px') == 2, f"Expected two cols at 1200px, got: {cols}"
    page.close()

    browser.close()
    print("Task 3 OK")
```

Run: `python ui-experiments/verify_t3.py`
Expected: `Task 3 OK`

**Step 3: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): add 1100px breakpoint — single column below this width"
```

---

## Task 4: Right panel empty state — collapsed

**Files:**
- Modify: `src/ui/index.html:106-130` (CSS for `.job-history-panel` and `.job-history-empty`)

**Step 1: Update `.job-history-panel`**

Find lines 106–109 (`.job-history-panel` rule):
```css
        .job-history-panel {
            margin-bottom: 1.5rem;
        }
```
Replace with:
```css
        .job-history-panel {
            min-height: 0;
            margin-bottom: 1.5rem;
        }
```

**Step 2: Update `.job-history-empty`**

Find the `.job-history-empty` rule (~line 127). Add `font-size: 0.85rem;`:
```css
        .job-history-empty {
            /* existing rules stay unchanged */
            font-size: 0.85rem;
        }
```
(Only add the font-size line; keep whatever rules are already there.)

**Step 3: Verify with Playwright**

```python
# save as ui-experiments/verify_t4.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')
    panel_height = page.evaluate('document.querySelector(".job-history-panel").offsetHeight')
    right_height  = page.evaluate('document.querySelector(".right-column").offsetHeight')
    print(f"Panel height (empty): {panel_height}px, Right col height: {right_height}px")
    # Panel should be small (no forced min-height), not 500+ px
    assert panel_height < 200, f"Panel too tall when empty: {panel_height}px"
    page.screenshot(path=str(OUT / "t4-empty-state.png"))
    browser.close()
    print("Task 4 OK")
```

Run: `python ui-experiments/verify_t4.py`
Expected: `Task 4 OK`

**Step 4: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): collapse empty job-history-panel (min-height: 0)"
```

---

## Task 5: Remove `.right-column .buttons` CSS rule

**Files:**
- Modify: `src/ui/index.html:195-200`

**Step 1: Delete the CSS rule**

Find and delete these 4 lines (~195–200):
```css
        /* Right column execute button */
        .right-column .buttons {
            margin-bottom: 1rem;
        }
```

**Step 2: No separate verification needed** — this is a dead rule once the HTML is cleaned up in Task 6. Visual check via screenshot after Task 6 is sufficient.

**Step 3: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): remove dead .right-column .buttons CSS rule"
```

---

## Task 6: Remove duplicate buttons from right column (HTML + JS)

**Files:**
- Modify: `src/ui/index.html:1310-1315` (HTML)
- Modify: `src/ui/index.html:1363-1364` (JS declarations)
- Modify: `src/ui/index.html:1436-1441` (JS event listeners)

> **Note:** Line numbers will have shifted by ~4 lines after Task 5. Use text search to find the exact locations.

**Step 1: Delete the right column buttons HTML block**

Find and delete this block (after the `job-history-panel` closing div, before `phase-banner`):
```html
                <!-- Execute Button for Right Column -->
                <div class="buttons">
                    <button type="button" class="btn-primary" id="startBtnRight">▶ EXECUTE CRAWL</button>
                    <button type="button" class="btn-danger" id="cancelBtnRight">■ ABORT</button>
                </div>
```

**Step 2: Delete the JS variable declarations**

Find and delete these two lines:
```js
        const startBtnRight = document.getElementById('startBtnRight');
        const cancelBtnRight = document.getElementById('cancelBtnRight');
```

**Step 3: Delete the JS event listeners**

Find and delete this block (7 lines total including the comment):
```js
        // Sync right column buttons with left
        startBtnRight.addEventListener('click', () => form.dispatchEvent(new Event('submit')));
        cancelBtnRight.addEventListener('click', () => {
            if (currentJobId) {
                stopJob(currentJobId);
            }
        });
```

**Step 4: Verify with Playwright**

```python
# save as ui-experiments/verify_t6.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')

    # startBtnRight must not exist
    right_btn = page.query_selector('#startBtnRight')
    assert right_btn is None, "startBtnRight still exists in DOM"

    # No JS errors on page
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.reload()
    page.wait_for_load_state('networkidle')
    assert not errors, f"JS errors after removal: {errors}"

    # The main startBtn still works
    start_btn = page.query_selector('#startBtn')
    assert start_btn is not None, "startBtn missing"

    page.screenshot(path=str(OUT / "t6-no-duplicate-button.png"))
    browser.close()
    print("Task 6 OK")
```

Run: `python ui-experiments/verify_t6.py`
Expected: `Task 6 OK`

**Step 5: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): remove duplicate #startBtnRight and its JS listeners"
```

---

## Task 7: Move Execute button up in form

**Files:**
- Modify: `src/ui/index.html` — form HTML structure

**Context:** Currently the `<div class="buttons">` with `#startBtn` and `#cancelBtn` is at the very bottom of the form (after all checkboxes, output format, converter, markdown optimization). The goal is to move it to just before the first `<div class="checkbox-group">` (before `respectRobots`), so it sits after the essential config fields (URL, models, depth, pages, concurrency, language) and before the optional checkboxes.

**Step 1: Find the buttons div**

Search for:
```html
            <div class="buttons">
                <button type="submit" class="btn-primary" id="startBtn">▶ EXECUTE CRAWL</button>
                <button type="button" class="btn-danger" id="cancelBtn">■ ABORT</button>
            </div>
        </form>
```

**Step 2: Cut it from its current position**

Delete that `<div class="buttons">...</div>` block from the bottom of the form (the `</form>` tag stays where it is).

**Step 3: Paste it before the first checkbox-group**

Find the first `<div class="checkbox-group">` in the form (the one with `id="respectRobots"`):
```html
            <div class="checkbox-group">
                <input type="checkbox" id="respectRobots" checked>
                <label for="respectRobots">Respect robots.txt Protocol</label>
            </div>
```

Insert the buttons div **immediately before** it:
```html
            <div class="buttons">
                <button type="submit" class="btn-primary" id="startBtn">▶ EXECUTE CRAWL</button>
                <button type="button" class="btn-danger" id="cancelBtn">■ ABORT</button>
            </div>

            <div class="checkbox-group">
                <input type="checkbox" id="respectRobots" checked>
```

**Step 4: Verify with Playwright**

```python
# save as ui-experiments/verify_t7.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:8002/')
    page.wait_for_load_state('networkidle')

    # Button should be above the respectRobots checkbox
    positions = page.evaluate('''() => {
        const btn  = document.getElementById("startBtn").getBoundingClientRect();
        const chk  = document.getElementById("respectRobots").getBoundingClientRect();
        return { btnTop: btn.top, chkTop: chk.top }
    }''')
    print("Positions:", positions)
    assert positions['btnTop'] < positions['chkTop'], \
        f"Button ({positions['btnTop']}) should be above checkbox ({positions['chkTop']})"

    # Form should still submit (button is type=submit inside the form)
    form_exists = page.evaluate('!!document.getElementById("crawlForm")')
    assert form_exists, "Form not found"

    page.screenshot(path=str(OUT / "t7-button-moved-up.png"))
    browser.close()
    print("Task 7 OK")
```

Run: `python ui-experiments/verify_t7.py`
Expected: `Task 7 OK`

**Step 5: Commit**
```bash
git add src/ui/index.html
git commit -m "fix(ui): move Execute Crawl button above advanced options"
```

---

## Task 8: Full visual verification — all viewports

**Step 1: Run the full verification suite**

```python
# save as ui-experiments/verify_final.py
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")

VIEWPORTS = [
    (1920, 1080, "1920x1080"),
    (1440, 900,  "1440x900"),
    (1200, 800,  "1200x800"),
    (1099, 800,  "1099x800-single-col"),
    (900,  700,  "900x700-mobile"),
]

INJECT_CONTENT = """() => {
    const logDiv = document.querySelector('.log');
    if (logDiv) {
        logDiv.style.display = 'block';
        logDiv.innerHTML = '<div class="log-entry">[00:01] Crawling https://docs.example.com/</div><div class="log-entry">[00:02] Discovery: 12 URLs found at depth 0</div><div class="log-entry">[00:03] Scraping intro - LLM cleanup applied</div>';
    }
    const histList = document.querySelector('.job-history-list');
    if (histList) {
        histList.innerHTML = '<div style="padding:8px;border-bottom:1px solid #2a2a4a">docs.example.com - completed</div><div style="padding:8px;color:#00ffff">react.dev - running</div>';
    }
    const empty = document.querySelector('.job-history-empty');
    if (empty) empty.style.display = 'none';
}"""

with sync_playwright() as p:
    browser = p.chromium.launch()

    for w, h, name in VIEWPORTS:
        for theme in ['synthwave', 'basic', 'terminal']:
            page = browser.new_page(viewport={'width': w, 'height': h})
            page.goto('http://localhost:8002/')
            page.wait_for_load_state('networkidle')
            page.select_option('.theme-selector select', theme)
            page.wait_for_timeout(200)
            page.evaluate(INJECT_CONTENT)
            page.wait_for_timeout(200)
            page.screenshot(path=str(OUT / f"final-{name}-{theme}.png"))
            page.close()
            print(f"OK: {name} / {theme}")

    browser.close()

print("Final verification done. Screenshots in:", OUT)
```

Run: `python ui-experiments/verify_final.py`
Expected: 15 screenshots generated, no errors.

**Step 2: Open the screenshots and visually inspect:**
- `final-1920x1080-synthwave.png` — 1600px container, 65/35 grid, right panel sticky, single Execute button visible
- `final-1099x800-single-col-*.png` — single column layout, no sticky
- `final-900x700-mobile-*.png` — existing responsive styles, unchanged

**Step 3: Final commit + push**

```bash
git add src/ui/index.html
git commit -m "chore: cleanup ui-experiments runner scripts"

git push origin main
```

---

## Checklist

- [ ] Task 1: Container `min(1600px, 100vw-48px)` ✓ Playwright verify
- [ ] Task 2: Grid 65/35, right column sticky ✓ Playwright verify
- [ ] Task 3: Breakpoint 1100px ✓ Playwright verify
- [ ] Task 4: Empty panel collapses ✓ Playwright verify
- [ ] Task 5: Dead CSS rule removed
- [ ] Task 6: Duplicate button removed, no JS errors ✓ Playwright verify
- [ ] Task 7: Execute button moved above checkboxes ✓ Playwright verify
- [ ] Task 8: Full visual verification — 15 screenshots across 5 viewports × 3 themes
