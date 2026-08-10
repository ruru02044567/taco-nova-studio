"""上傳並公開發布到 Taco & Nova 頻道，含合規設定。
用法：python publish_video.py <video.mp4> <title.txt> <desc.txt>
成功時會印出一行含 youtube.com/shorts/ 的網址。
"""
import sys
import time

from playwright.sync_api import sync_playwright

video, title_file, desc_file = sys.argv[1], sys.argv[2], sys.argv[3]
title = open(title_file, encoding="utf-8").read().strip()
desc = open(desc_file, encoding="utf-8").read().strip()

WANT = ["VIDEO_MADE_FOR_KIDS_NOT_MFK", "VIDEO_AGE_RESTRICTION_NONE", "VIDEO_HAS_ALTERED_CONTENT_YES"]


def click_exact(page, text):
    return page.evaluate(
        """(t) => {
            for (const el of document.querySelectorAll('button, ytcp-button, tp-yt-paper-button')) {
                if ((el.innerText || '').trim() === t) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0) { el.click(); return true; }
                }
            }
            return false;
        }""",
        text,
    )


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "youtube.com" in p.url and "gemini" not in p.url), None) \
        or ctx.new_page()
    page.bring_to_front()

    page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded")
    time.sleep(6)
    with page.expect_file_chooser(timeout=20000) as fc:
        page.get_by_text("選取檔案").first.click()
    fc.value.set_files(video)
    time.sleep(12)
    print("file selected")

    up = next(p for p in ctx.pages if "videos/upload" in p.url)
    up.bring_to_front()
    time.sleep(4)

    up.get_by_role("textbox", name="新增可描述影片內容的標題").first.fill(title)
    up.get_by_role("textbox", name="向觀眾介紹你的影片").first.fill(desc)
    time.sleep(2)
    print("details filled")

    # 展開「顯示更多」才看得到 AI 使用區塊
    for _ in range(2):
        if click_exact(up, "顯示更多"):
            time.sleep(3)
            break
        time.sleep(1)

    radios = {}
    for r in up.locator("tp-yt-paper-radio-button").all():
        n = r.get_attribute("name") or ""
        if n:
            radios[n] = r
    for want in WANT:
        if want in radios:
            radios[want].evaluate("el => el.click()")
            time.sleep(1)
    print("compliance:", {w: (radios[w].get_attribute("aria-checked") if w in radios else "MISSING")
                          for w in WANT})

    for _ in range(3):
        click_exact(up, "下一步")
        time.sleep(3)

    picked = False
    for r in up.locator("tp-yt-paper-radio-button").all():
        if (r.get_attribute("name") or "").upper() == "PUBLIC":
            r.evaluate("el => el.click()")
            picked = True
            break
    if not picked:
        print("FAILED: 找不到公開選項")
        sys.exit(1)
    time.sleep(2)

    url = ""
    try:
        url = up.locator("a[href*='youtube.com/shorts'], a[href*='youtu.be']").first.get_attribute("href")
    except Exception:
        pass

    if not click_exact(up, "發布"):
        print("FAILED: 沒按到發布")
        sys.exit(1)
    time.sleep(8)
    print("PUBLISHED", url)
