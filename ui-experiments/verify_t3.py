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
