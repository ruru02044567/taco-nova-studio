# -*- coding: utf-8 -*-
"""看 Gemini 頁面現在到底長怎樣：是額度用完、還是影片生好了但按鈕找不到"""
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None)
    if not page:
        print("找不到 Gemini 分頁")
        sys.exit(1)

    print("URL:", page.url)
    page.screenshot(path="diag-gemini.png", full_page=False)
    print("已截圖 diag-gemini.png")

    body = page.evaluate("() => document.body.innerText")
    print("\n===== 頁面文字（後 1800 字）=====")
    print(body[-1800:])

    print("\n===== 所有按鈕的 aria-label =====")
    labels = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[aria-label]').forEach(el => {
            const l = el.getAttribute('aria-label');
            const r = el.getBoundingClientRect();
            if (l && r.width > 0) out.push(l);
        });
        return [...new Set(out)];
    }""")
    for l in labels:
        print(" -", l)

    print("\n===== 頁面上有幾個 video 元素 =====")
    print(page.evaluate("() => document.querySelectorAll('video').length"))
