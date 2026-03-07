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
