# -*- coding: utf-8 -*-
"""只讀不寫地查 Gemini／Veo 現在還能不能生影片。

跟 make_video_cloud.py 的差別：**這支絕對不送出任何 prompt**，
只進到影片模式、把畫面上跟額度有關的字撈出來、拍一張截圖。
用途是排程或人工要決定「今天走雲端還是本機」時，先問一句不花額度的話。

⚠️ 已知限制（不要對這支的輸出過度解讀）：
    Gemini 的免費額度**不會**在介面上顯示剩餘數字。
    「還剩幾支」只有在額度用完之後、它跳出那句英文提示時才知道。
    所以這支只能回答三種狀態：
        EXHAUSTED  畫面上出現了額度用完的提示 → 確定不能用
        NO_LIMIT_SHOWN  進得去影片模式、沒有任何額度警告 → 很可能可用，但沒有保證
        BLOCKED    連影片模式都進不去（多半是沒登入或版面又改了）
    要 100% 確認只有真的送一支出去，那就會消耗額度 —— 由呼叫的人決定要不要。

用法：python veo_quota.py [--screenshot 路徑.png]
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

QUOTA_MARKS = ["out of videos", "Upgrade to keep creating", "Videos are only free",
               "You've reached your limit", "額度", "已用完"]
# 有些版面會把剩餘數量寫在按鈕旁邊，撈到就記下來（目前沒實際看過，備著）
COUNT_HINTS = ["videos left", "remaining", "剩餘", "還可以"]

shot = None
if "--screenshot" in sys.argv:
    shot = sys.argv[sys.argv.index("--screenshot") + 1]

result = {"status": "UNKNOWN", "quota_text": "", "hints": [], "video_mode": False}

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None)
    if page is None:
        page = ctx.new_page()
        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
        time.sleep(8)
    page.bring_to_front()
    time.sleep(2)

    def body():
        try:
            return page.evaluate("() => document.body.innerText") or ""
        except Exception:
            return ""

    def video_mode_on():
        return page.evaluate(
            "() => !!document.querySelector(\"[aria-label*='顯示比例']\")")

    # 進影片模式。正解是左側工具列那顆「影片」——「上傳與工具 → 建立影片」
    # 點得到但模式不會真的開（8/10 踩過，見 make_video_cloud.py 的註解）
    for _ in range(3):
        if video_mode_on():
            break
        try:
            page.locator("[aria-label='影片']").first.click(timeout=8000)
            time.sleep(5)
        except Exception:
            time.sleep(2)
    result["video_mode"] = bool(video_mode_on())

    txt = body()
    for m in QUOTA_MARKS:
        if m in txt:
            for line in txt.splitlines():
                if m in line:
                    result["quota_text"] = line.strip()[:200]
                    break
            result["quota_text"] = result["quota_text"] or m
            break
    for h in COUNT_HINTS:
        for line in txt.splitlines():
            if h in line:
                result["hints"].append(line.strip()[:150])

    # 順便記下模型選單上寫的是哪一版（Veo 版本會影響畫質與額度算法）
    try:
        result["model_label"] = page.evaluate(
            """() => {
                const el = document.querySelector("[aria-label*='模型']")
                       || document.querySelector('bard-mode-switcher button');
                return el ? (el.innerText || el.getAttribute('aria-label') || '').trim() : '';
            }""")[:100]
    except Exception:
        result["model_label"] = ""

    if result["quota_text"]:
        result["status"] = "EXHAUSTED"
    elif result["video_mode"]:
        result["status"] = "NO_LIMIT_SHOWN"
    else:
        result["status"] = "BLOCKED"

    if shot:
        Path(shot).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=shot, full_page=False)
        result["screenshot"] = shot

print(json.dumps(result, ensure_ascii=False, indent=2))
