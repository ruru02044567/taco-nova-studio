# -*- coding: utf-8 -*-
"""測「左側工具列的影片按鈕」能不能直接進影片模式"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")


def state(page):
    return page.evaluate("""() => ({
        aspect: !!document.querySelector("[aria-label*='顯示比例']"),
        chip: !!document.querySelector("[aria-label*='取消選取']"),
        url: location.href,
        heading: (document.querySelector('h1,h2')||{}).innerText || ''
    })""")


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None) or ctx.new_page()
    page.bring_to_front()
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    time.sleep(6)
    print("起始:", state(page))

    # 左側工具列那顆「影片」
    try:
        page.locator("[aria-label='影片']").first.click(timeout=8000)
        print("點了左側「影片」")
    except Exception as e:
        print("點不到左側「影片」:", str(e)[:90])

    time.sleep(6)
    print("點完:", state(page))
    page.screenshot(path="diag-click.png")
    print("已截圖")
