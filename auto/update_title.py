# -*- coding: utf-8 -*-
"""改已發布影片的標題（只動標題，其他一律不碰）。

用法：python update_title.py <videoId> "<新標題>"

⚠️ 改已發布影片的標題會讓演算法重新學習這支片，短期數據可能波動。
不要為了 A/B 隨便改，要改就是有明確理由的一次性修正。
"""
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

sys.stdout.reconfigure(encoding="utf-8")
acquire("update_title")

vid, new_title = sys.argv[1], sys.argv[2]

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = b.contexts[0].new_page()
    page.goto(f"https://studio.youtube.com/video/{vid}/edit",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(9)

    if "studio.youtube.com" not in page.url:
        print(f"FAILED: 沒進到 Studio（可能要重新登入）→ {page.url}")
        sys.exit(2)

    # 標題欄跟說明欄一樣是 contenteditable，不是 input
    box = None
    for sel in ["#title-textarea #textbox",
                "ytcp-video-title #textbox",
                "#title-container #textbox",
                "#title #textbox"]:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=8000)
            box = loc
            print(f"找到標題欄：{sel}")
            break
        except Exception:
            continue
    if not box:
        print("FAILED: 找不到標題欄")
        page.screenshot(path=f"_診斷截圖/title_fail_{vid}.png")
        sys.exit(3)

    before = (box.inner_text() or "").strip()
    print(f"原標題：{before}")
    if before == new_title:
        print("標題已經是目標值，不動作")
        page.close()
        sys.exit(0)

    box.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    time.sleep(1)
    page.keyboard.insert_text(new_title)
    time.sleep(2)

    after = (box.inner_text() or "").strip()
    print(f"新標題：{after}")
    if after != new_title:
        print(f"FAILED: 填進去的跟預期不符")
        page.screenshot(path=f"_診斷截圖/title_mismatch_{vid}.png")
        sys.exit(4)

    saved = False
    for _ in range(3):
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('ytcp-button, button')) {
                const t = (el.innerText || '').trim();
                if (t === '儲存' || t === 'Save') { el.click(); return true; }
            }
            return false;
        }""")
        time.sleep(5)
        body = page.evaluate("() => document.body.innerText || ''")
        if "變更已儲存" in body or "Changes saved" in body or "已儲存" in body:
            saved = True
            break
    print("SAVED" if saved else "WARN: 沒看到「已儲存」提示，請人工確認")
    page.close()
    sys.exit(0 if saved else 5)
