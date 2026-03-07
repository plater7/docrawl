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
