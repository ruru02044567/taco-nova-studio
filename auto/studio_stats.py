# -*- coding: utf-8 -*-
"""從 YouTube Studio 抓公開 API 拿不到的數據：曝光、點閱率、平均完播率"""
import re
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
CH = "UC4Bf0lB05GrYF8Q4l6NnjEA"


def dump(page, tag, wait=25):
    time.sleep(wait)
    for _ in range(3):                      # Studio 的圖表要捲到才載
        page.mouse.wheel(0, 700)
        time.sleep(3)
    page.screenshot(path=f"studio-{tag}.png", full_page=True)
    txt = page.evaluate("() => document.body.innerText")
    # 去掉左側導覽那串固定文字
    for junk in ["頻道數據分析", "略過導覽", "建立", "你的頻道", "Taco & Nova", "資訊主頁",
                 "內容", "數據分析", "社群", "字幕", "內容偵測", "營利", "自訂", "音樂庫",
                 "設定", "提供意見"]:
        txt = txt.replace(junk + "\n", "")
    txt = re.sub(r"\n{2,}", "\n", txt).strip()
    print(f"\n========== {tag} ==========")
    print(txt[:2500])
    return txt


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = b.contexts[0].new_page()

    page.goto(f"https://studio.youtube.com/channel/{CH}/analytics/tab-reach/period-default",
              wait_until="domcontentloaded")
    dump(page, "reach")

    page.goto(f"https://studio.youtube.com/channel/{CH}/analytics/tab-overview/period-default",
              wait_until="domcontentloaded")
    dump(page, "overview")
