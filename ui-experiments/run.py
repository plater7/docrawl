import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path("C:/claude-code/docrawl/ui-experiments")
OUT.mkdir(exist_ok=True)

CSS_EXPERIMENTS = {
    "1200-baseline": "",
    "1400-50-50": ".container { max-width: 1400px !important; padding: 0 24px !important; }",
    "1600-50-50": ".container { max-width: 1600px !important; padding: 0 24px !important; }",
    "1600-55-45-sticky": """
        .container { max-width: 1600px !important; padding: 0 24px !important; }
        .two-columns { display: grid !important; grid-template-columns: 55% 45% !important; gap: 24px !important; align-items: start !important; }
        .right-column { position: sticky !important; top: 16px !important; max-height: calc(100vh - 80px) !important; overflow-y: auto !important; }
        .job-history-panel { min-height: 500px !important; }
    """,
    "1600-60-40-sticky": """
        .container { max-width: 1600px !important; padding: 0 24px !important; }
        .two-columns { display: grid !important; grid-template-columns: 60% 40% !important; gap: 24px !important; align-items: start !important; }
        .right-column { position: sticky !important; top: 16px !important; max-height: calc(100vh - 80px) !important; overflow-y: auto !important; }
        .job-history-panel { min-height: 500px !important; }
    """,
    "1600-65-35-sticky": """
        .container { max-width: 1600px !important; padding: 0 24px !important; }
        .two-columns { display: grid !important; grid-template-columns: 65% 35% !important; gap: 32px !important; align-items: start !important; }
        .right-column { position: sticky !important; top: 16px !important; max-height: calc(100vh - 80px) !important; overflow-y: auto !important; }
        .job-history-panel { min-height: 500px !important; }
    """,
}

INJECT = """() => {
    const logDiv = document.querySelector('.log');
    if (logDiv) {
        logDiv.style.display = 'block';
        logDiv.innerHTML = '<div class="log-entry">[00:01] Crawling https://docs.example.com/</div><div class="log-entry">[00:02] Discovery: 12 URLs found at depth 0</div><div class="log-entry">[00:03] Scraping intro - LLM cleanup applied</div><div class="log-entry">[00:04] Scraping api reference - 2400 chars</div><div class="log-entry">[00:05] Scraping guide - complete</div>';
    }
    const histList = document.querySelector('.job-history-list');
    if (histList) {
        histList.innerHTML = '<div style="padding:8px;border-bottom:1px solid #2a2a4a">docs.example.com - completed</div><div style="padding:8px;border-bottom:1px solid #2a2a4a">api.stripe.com - completed</div><div style="padding:8px;color:#00ffff">react.dev - running</div>';
    }
    const empty = document.querySelector('.job-history-empty');
    if (empty) empty.style.display = 'none';
}"""

with sync_playwright() as p:
    browser = p.chromium.launch()

    for name, css in CSS_EXPERIMENTS.items():
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto('http://localhost:8002/')
        page.wait_for_load_state('networkidle')
        if css.strip():
            safe_css = css.replace('`', r'\`').replace('${', r'\${')
            page.evaluate(f'() => {{ const s=document.createElement("style"); s.textContent=`{safe_css}`; document.head.appendChild(s); }}')
        page.evaluate(INJECT)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / f"{name}.png"))
        page.close()
        print(f"OK: {name}")

    # zoom variants on best candidate (55/45)
    css = CSS_EXPERIMENTS["1600-55-45-sticky"]
    safe_css = css.replace('`', r'\`').replace('${', r'\${')
    for zoom in [0.85, 0.9, 1.0]:
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto('http://localhost:8002/')
        page.wait_for_load_state('networkidle')
        page.evaluate(f'() => {{ const s=document.createElement("style"); s.textContent=`{safe_css}`; document.head.appendChild(s); document.body.style.zoom="{zoom}"; }}')
        page.evaluate(INJECT)
        page.wait_for_timeout(300)
        zname = str(zoom).replace('.','_')
        page.screenshot(path=str(OUT / f"zoom-{zname}.png"))
        page.close()
        print(f"OK: zoom {zoom}")

    browser.close()

print("Done:", OUT)
