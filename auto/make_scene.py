# -*- coding: utf-8 -*-
"""用 Gemini 生場景圖（免費、不佔影片額度）。用法：python make_scene.py <prompt.txt> <out.jpg>

2026-08-09 改版，修掉三個會讓生圖靜默失敗的坑（舊版留在 make_scene.py.bak）：

1. **先確認沒卡在影片模式**。Edge 用的是固定 profile，前一輪生影片留下的「影片」模式
   會黏在新對話上，於是生圖請求被路由去 Veo，直接回「You're out of videos」——
   看起來像生圖壞了，其實是被當成影片扣掉了當天的影片額度。
2. **prompt 前面加一句 `Generate an image:`**。舊 prompt 開頭寫 "photorealistic home video still"，
   有 video 字樣，Gemini 有機會自己判斷成要生影片。
3. **CDP 連 127.0.0.1 而不是 localhost**。localhost 在這台機器會先解析成 IPv6 的 ::1，
   Edge 只聽 IPv4，於是 connect ECONNREFUSED ::1:9222。

撞到額度訊息時直接 exit 2，不再傻等三輪重試。
"""
import base64
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

acquire("make_scene")            # 跟排程器搶同一個 Edge 會互相把對話沖掉

sys.stdout.reconfigure(encoding="utf-8")

prompt_file, out = sys.argv[1], sys.argv[2]
prompt = "Generate an image:\n\n" + open(prompt_file, encoding="utf-8").read().strip()

GRAB = """
() => {
    const imgs = Array.from(document.querySelectorAll('img'))
        .filter(i => i.naturalWidth > 400 && i.naturalHeight > 400);
    if (!imgs.length) return null;
    const img = imgs[imgs.length - 1];
    const c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    c.getContext('2d').drawImage(img, 0, 0);
    return c.toDataURL('image/jpeg', 0.95);
}
"""

# 額度／錯誤訊息。撞到就直接停，不要重試三次浪費時間
FAIL_MARKS = ["out of videos", "Videos are only free", "Upgrade to keep creating"]


def video_mode_on(page):
    return page.evaluate(
        """() => !!document.querySelector("[aria-label*='取消選取'][aria-label*='影片']")
              || !!document.querySelector("[aria-label*='顯示比例']")""")


def leave_video_mode(page):
    """影片模式黏著時把它關掉，否則生圖會被當成生影片。"""
    for _ in range(3):
        if not video_mode_on(page):
            return True
        clicked = page.evaluate("""() => {
            const el = document.querySelector("[aria-label*='取消選取'][aria-label*='影片']");
            if (el) { el.click(); return true; }
            return false;
        }""")
        if not clicked:
            page.keyboard.press("Escape")
        time.sleep(2)
    return not video_mode_on(page)


def new_chat(page):
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    try:
        page.locator("div[contenteditable='true'], rich-textarea div").first.wait_for(timeout=30000)
    except Exception:
        pass
    time.sleep(2)


def grab(page):
    """抓圖。送出後 Gemini 會換網址，撞到導航就當這次沒抓到，別讓腳本死掉。"""
    try:
        return page.evaluate(GRAB)
    except Exception:
        return None


def body_text(page):
    try:
        return page.evaluate("() => document.body.innerText")
    except Exception:
        return ""


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None) or ctx.new_page()
    page.bring_to_front()

    for attempt in range(3):
        new_chat(page)
        if not leave_video_mode(page):
            print("FAILED: 影片模式關不掉，生圖會被當成生影片")
            sys.exit(1)

        box = page.locator("div[contenteditable='true'], rich-textarea div").first
        box.click()
        # 不能用 box.type()：逐字打字，2000 字以上會撞 30 秒逾時
        page.keyboard.insert_text(prompt[:4000])
        time.sleep(1.5)
        page.keyboard.press("Enter")
        print(f"attempt {attempt + 1}: prompt sent")

        data = None
        for _ in range(24):          # 最多等 120 秒
            time.sleep(5)
            txt = body_text(page)
            if any(m in txt for m in FAIL_MARKS):
                print("FAILED: 被當成影片請求，額度已用完（生圖不該走到這裡）")
                sys.exit(2)
            data = grab(page)
            if data:
                break
        if data:
            with open(out, "wb") as f:
                f.write(base64.b64decode(data.split(",", 1)[1]))
            print("saved", out)
            sys.exit(0)
        print("no image this attempt, retrying")

    print("FAILED: no image after 3 attempts")
    sys.exit(1)
