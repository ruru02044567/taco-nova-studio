# -*- coding: utf-8 -*-
"""用 Gemini 改圖：掛一張參考圖，要求同房間同機位只換動作 → 多鏡頭背景一致。

用法：python make_scene_ref.py <prompt.txt> <out.jpg> <ref.jpg>
不給 ref.jpg 就跟 make_scene.py 一樣純文字生圖。

跟 make_scene.py 的差別：
1. 會先把參考圖上傳再打字（上傳鈕可能藏在「上傳與工具」選單裡，兩層找）
2. 抓圖改用「數量比較法」：上傳的參考圖本身也是一張大 <img>，
   不能傻抓「最後一張大圖」，要等大圖數量比送出前多才算生成完成
"""
import base64
import sys
import time

from browser_lock import acquire

acquire("make_scene_ref")        # 跟排程器搶同一個 Edge 會互相把對話沖掉

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

prompt_file, out = sys.argv[1], sys.argv[2]
ref = sys.argv[3] if len(sys.argv) > 3 else None
prompt = "Generate an image:\n\n" + open(prompt_file, encoding="utf-8").read().strip()

COUNT = """
() => Array.from(document.querySelectorAll('img'))
        .filter(i => i.naturalWidth > 400 && i.naturalHeight > 400).length
"""

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

FAIL_MARKS = ["out of videos", "Videos are only free", "Upgrade to keep creating"]


def video_mode_on(page):
    return page.evaluate(
        """() => !!document.querySelector("[aria-label*='取消選取'][aria-label*='影片']")
              || !!document.querySelector("[aria-label*='顯示比例']")""")


def leave_video_mode(page):
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


def attach(page, path):
    """上傳參考圖。先找可見的上傳鈕，沒有就開「上傳與工具」選單再找。"""
    for round_ in range(2):
        cands = [c for c in page.locator("[aria-label^='上傳檔案']").all() if c.is_visible()]
        if cands:
            with page.expect_file_chooser(timeout=15000) as fc:
                cands[-1].click()
            fc.value.set_files(path)
            time.sleep(10)          # 等圖真的傳完，太早送出整包會被吃掉
            return True
        if round_ == 0:
            try:
                page.locator("[aria-label*='上傳與工具']").first.click(timeout=10000)
                time.sleep(2)
            except Exception:
                pass
    return False


def counted(page):
    try:
        return page.evaluate(COUNT)
    except Exception:
        return -1


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
            print("FAILED: 影片模式關不掉")
            sys.exit(1)

        if ref:
            if not attach(page, ref):
                print(f"attempt {attempt + 1}: 找不到上傳按鈕，重試")
                continue
            print(f"attempt {attempt + 1}: ref attached")

        base = counted(page)         # 送出前的大圖數（含剛上傳的參考圖）
        box = page.locator("div[contenteditable='true'], rich-textarea div").first
        box.click()
        page.keyboard.insert_text(prompt[:4000])
        time.sleep(1.5)
        page.keyboard.press("Enter")
        print(f"attempt {attempt + 1}: prompt sent (base imgs={base})")

        data = None
        for _ in range(36):          # 最多等 180 秒（改圖比生圖慢）
            time.sleep(5)
            txt = body_text(page)
            if any(m in txt for m in FAIL_MARKS):
                print("FAILED: 被當成影片請求，額度已用完")
                sys.exit(2)
            now = counted(page)
            if now > max(base, 0):   # 大圖變多＝新圖生出來了
                data = page.evaluate(GRAB)
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
