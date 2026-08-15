# -*- coding: utf-8 -*-
"""接手監看已經在生成中的 Gemini 影片，好了就下載。
用法：python watch_video.py <out.mp4> [等幾分鐘]
"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
out = sys.argv[1]
minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 20

FAIL_MARKS = ["發生錯誤", "getting a lot of requests", "請檢查你的網際網路連線",
              "something went wrong", "try again later",
              # 額度用完時 Gemini 只會用英文講這句，之前沒收進來，一路被誤判成「逾時」
              "out of videos", "Upgrade to keep creating", "Videos are only free"]

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None)
    if not page:
        print("找不到 Gemini 分頁")
        sys.exit(1)

    for i in range(minutes * 6):
        time.sleep(10)
        try:
            body = page.evaluate("() => document.body.innerText")
            nvid = page.evaluate("() => document.querySelectorAll('video').length")
            has_dl = page.evaluate(
                """() => !!document.querySelector("[aria-label*='下載'], [aria-label*='Download']")""")
        except Exception:
            continue

        if i % 6 == 0:
            state = "分析中" if "正在分析" in body else ("生成中" if "生成" in body else "?")
            print(f"  [{i // 6} 分] {state}  video={nvid}  下載鈕={has_dl}", flush=True)

        if any(m in body for m in FAIL_MARKS):
            print("FAILED: 頁面出現錯誤／額度訊息")
            print([m for m in FAIL_MARKS if m in body])
            sys.exit(1)

        if has_dl:
            try:
                btn = page.locator("[aria-label*='下載']").last
                with page.expect_download(timeout=120000) as dl:
                    btn.click()
                dl.value.save_as(out)
                print("saved", out)
                sys.exit(0)
            except Exception as e:
                print("下載按鈕點了但沒抓到檔案：", str(e)[:120])

        if nvid > 0:
            src = page.evaluate("""() => {
                const v = document.querySelector('video');
                return v ? (v.currentSrc || v.src || '') : '';
            }""")
            print("頁面已出現影片元素，src:", src[:120])

    print("FAILED: 等了", minutes, "分鐘還是沒好")
    sys.exit(1)
