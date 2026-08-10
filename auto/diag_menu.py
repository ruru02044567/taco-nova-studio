# -*- coding: utf-8 -*-
"""點開「上傳與工具」選單，看裡面到底有哪些選項"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None)
    if not page:
        print("找不到 Gemini 分頁")
        sys.exit(1)

    print("目前 URL:", page.url)
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    time.sleep(6)
    page.bring_to_front()

    try:
        page.locator("[aria-label*='上傳與工具']").first.click(timeout=10000)
        print("已點開『上傳與工具』")
    except Exception as e:
        print("點不開『上傳與工具』：", str(e)[:100])

    time.sleep(3)
    items = page.evaluate("""() => {
        const out = [];
        const sel = 'button, [role=button], [role=menuitem], span, div, tp-yt-paper-item, li';
        for (const el of document.querySelectorAll(sel)) {
            if (el.querySelector('*')) continue;
            const s = (el.innerText || '').trim();
            const r = el.getBoundingClientRect();
            if (s && s.length < 24 && r.width > 0 && r.height > 0) out.push(s);
        }
        return [...new Set(out)];
    }""")
    print("\n===== 畫面上可點的文字 =====")
    for s in items:
        print(" -", s)

    page.screenshot(path="diag-menu.png")
    print("\n已截圖 diag-menu.png")
