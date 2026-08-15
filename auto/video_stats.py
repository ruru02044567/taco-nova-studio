# -*- coding: utf-8 -*-
"""抓 Studio 內容頁：每支影片的標題、觀看、曝光、點閱率、完播率。

studio_stats.py 抓的是頻道層級的總數，這支抓的是**逐支影片**的比較 ——
要判斷「換標題有沒有害到流量」只能看逐支。

用法：python video_stats.py
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

sys.stdout.reconfigure(encoding="utf-8")
acquire("video_stats")

CH = "UC4Bf0lB05GrYF8Q4l6NnjEA"

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = b.contexts[0].new_page()

    # 內容頁：一列一支片，含觀看數
    page.goto(f"https://studio.youtube.com/channel/{CH}/videos/short",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(12)
    for _ in range(3):
        page.mouse.wheel(0, 800)
        time.sleep(2)

    if "studio.youtube.com" not in page.url:
        print(f"FAILED: 沒進到 Studio（可能要重新登入）→ {page.url}")
        sys.exit(2)

    txt = page.evaluate("() => document.body.innerText || ''")
    txt = re.sub(r"\n{2,}", "\n", txt).strip()
    print("========== 內容頁 ==========")
    print(txt[:4000])

    page.screenshot(path="_診斷截圖/studio-videos.png", full_page=True)
    print("\n截圖：auto/_診斷截圖/studio-videos.png")
    page.close()
