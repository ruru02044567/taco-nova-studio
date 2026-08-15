# -*- coding: utf-8 -*-
"""改已發布影片的說明文字（不動標題、不動任何其他設定）。

用法：python update_desc.py <videoId> <desc.txt>

為什麼要有這支：
2026-08-11 比對出來的事實 —— 兩支高流量片（9,882 / 5.1 萬）的說明第 2 條
都是**第三人稱劇情描述**，而掉到 50~60 觀看的兩支都沒有它。
Shorts 沒有旁白也沒有字幕，那段文字是 YouTube 唯一讀得懂「這片在演什麼」的線索。

只碰說明欄，改完存檔就走。標題、縮圖、合規設定、播放清單一律不動 ——
那些是實驗變數，動了就分不出是誰的功勞。
"""
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

sys.stdout.reconfigure(encoding="utf-8")

acquire("update_desc")

vid, desc_file = sys.argv[1], sys.argv[2]
desc = open(desc_file, encoding="utf-8").read().strip()

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    page = ctx.new_page()
    page.goto(f"https://studio.youtube.com/video/{vid}/edit",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(8)

    if "studio.youtube.com" not in page.url:
        print(f"FAILED: 沒進到 Studio（可能要重新登入）→ {page.url}")
        sys.exit(2)

    # 說明欄：Studio 的說明框是 contenteditable，不是 textarea
    box = None
    for sel in ["#description-textarea #textbox",
                "ytcp-video-description #textbox",
                "#description-container #textbox"]:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=8000)
            box = loc
            print(f"找到說明欄：{sel}")
            break
        except Exception:
            continue
    if not box:
        print("FAILED: 找不到說明欄")
        page.screenshot(path=f"desc_fail_{vid}.png")
        sys.exit(3)

    before = (box.inner_text() or "").strip()
    print(f"原說明 {len(before)} 字元，前 60：{before[:60]!r}")

    box.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    time.sleep(1)
    page.keyboard.insert_text(desc)
    time.sleep(2)

    after = (box.inner_text() or "").strip()
    print(f"新說明 {len(after)} 字元")
    if len(after) < 50:
        print("FAILED: 新說明沒填進去")
        sys.exit(4)

    # 儲存
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
    page.screenshot(path=f"desc_done_{vid}.png")
    page.close()
