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
