"""把已經在 Gemini 上生好（或正在生）的影片收下來。斷線後重跑這支就好。

為什麼要有這支：生片的等待期長達 20 分鐘，對話視窗一斷、腳本就被砍，
但 Veo 在 Google 那邊還是照生。以前這種情況等於整支重生（浪費額度又浪費 20 分鐘），
其實只要重新連上那個對話、把下載鈕按下去就好。

用法：python veo_resume.py <out.mp4> [等待分鐘數，預設 25]
前提：遙控用的 Edge 還開著（CDP 9222），而且那個對話分頁沒被關掉。
"""
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

# 這支只是等和下載，不會自己開新對話，但排程器會 —— 沒卡位的話
# 等到一半就被它的 goto('/app') 把對話沖掉，看起來就像 Veo 自己斷線。
acquire("veo_resume")

out = sys.argv[1]
wait_min = int(sys.argv[2]) if len(sys.argv) > 2 else 25

QUOTA_MARKS = ["out of videos", "Upgrade to keep creating", "Videos are only free"]
BUSY_MARKS = ["發生錯誤", "getting a lot of requests", "請檢查你的網際網路連線",
              "something went wrong", "try again later"]
FAIL_MARKS = QUOTA_MARKS + BUSY_MARKS

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None)
    if not page:
        print("FAILED: 沒有 Gemini 分頁（Edge 被關掉了，只能整支重生）")
        sys.exit(2)
    print("接上對話:", page.url)

    def has_dl():
        return page.evaluate(
            """() => !!document.querySelector("[aria-label*='下載影片'], button[aria-label*='下載']")""")

    def wiped():
        """整條對話被清掉、退回範本頁 —— 8/10 傍晚新遇到的死法：
        Veo 生到第 8 分鐘自己斷線，訊息連同附件一起消失，prompt 被還原回輸入框。
        這種情況再等下去也不會有下載鈕，早點認賠去重生比較快。"""
        return page.evaluate(
            """() => {
                const box = document.querySelector('div.ql-editor');
                return !!box && (box.innerText || '').trim().length > 50;
            }""")

    for i in range(wait_min * 6):        # 每 10 秒看一次
        if has_dl():
            break
        body = page.evaluate("() => document.body.innerText") or ""
        hit = next((m for m in QUOTA_MARKS if m in body), None)
        if hit:
            print(f"FAILED: Veo 額度用完 → {hit}")
            sys.exit(6)
        hit = next((m for m in BUSY_MARKS if m in body), None)
        if hit:
            print(f"FAILED: Veo 服務錯誤 → {hit}")
            sys.exit(5)
        if wiped():
            print("FAILED: 對話被清空（生到一半斷線），要整支重生")
            sys.exit(7)
        if i % 6 == 0:                   # 每分鐘報一次，才知道它還活著
            print(f"  等待中 {i // 6} 分鐘")
        time.sleep(10)
    else:
        print(f"FAILED: 等滿 {wait_min} 分鐘還沒生好")
        sys.exit(1)

    btn = page.locator("[aria-label*='下載影片']").last
    with page.expect_download(timeout=90000) as dl:
        btn.click()
    dl.value.save_as(out)
    print("saved", out)
