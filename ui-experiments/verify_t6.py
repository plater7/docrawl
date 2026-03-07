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
