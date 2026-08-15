# -*- coding: utf-8 -*-
"""逐支影片抓觸及數據（曝光／已觀看比例等）。

為什麼一定要看這些：
判斷「換標題有沒有害到流量」，關鍵不是觀看數，是**曝光**。

    曝光低          → 演算法根本沒推，跟標題無關（標題只影響「推了之後點不點」）
    曝光高、點閱率低 → 這才是標題／封面的問題

搞錯這個區分，就會花力氣改標題去解一個不是標題造成的問題。

⚠️ Shorts 的指標跟一般影片不一樣：沒有「曝光點閱率」，
有的是「已觀看／已滑過」的比例。所以這支不寫死指標名稱，
而是等頁面真的載完之後，把整區文字倒出來。

用法：python video_reach.py <videoId> [videoId ...]
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

sys.stdout.reconfigure(encoding="utf-8")
acquire("video_reach")

# 左側導覽那串固定文字，抓下來只會洗版
JUNK = {"影片數據分析", "略過導覽", "建立", "頻道內容", "你的影片", "詳細資訊",
        "數據分析", "編輯器", "留言", "字幕", "著作權聲明", "剪輯片段",
        "設定", "提供意見", "進階模式", "頻道數據分析"}


def wait_loaded(page, timeout=60):
    """等到圖表真的 render 出來 —— 用「內容有沒有長出數字」判斷，不要憑時間猜。"""
    for _ in range(timeout // 2):
        body = page.evaluate("() => document.body.innerText || ''")
        # 載完的頁面會出現這些字其中之一
        if any(k in body for k in ("曝光", "已觀看", "觀看次數", "這部影片的觀眾")):
            time.sleep(3)          # 再給圖表一點時間補完
            return True
        time.sleep(2)
    return False


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = b.contexts[0].new_page()

    for vid in sys.argv[1:]:
        for tab in ("tab-reach", "tab-overview"):
            page.goto(f"https://studio.youtube.com/video/{vid}/analytics/{tab}/period-default",
                      wait_until="domcontentloaded", timeout=60000)
            ok = wait_loaded(page)
            for _ in range(3):
                page.mouse.wheel(0, 700)
                time.sleep(2)

            txt = page.evaluate("() => document.body.innerText || ''")
            lines = [ln.strip() for ln in re.sub(r"\n{2,}", "\n", txt).splitlines()
                     if ln.strip() and ln.strip() not in JUNK]

            print(f"\n========== {vid} / {tab} {'' if ok else '（逾時，可能沒載完）'} ==========")
            print("\n".join(lines[:45]))

    page.close()
