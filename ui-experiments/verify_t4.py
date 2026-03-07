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
    assert panel_height < 200, f"Panel too tall when empty: {panel_height}px"
    page.screenshot(path=str(OUT / "t4-empty-state.png"))
    browser.close()
    print("Task 4 OK")
