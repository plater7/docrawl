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
