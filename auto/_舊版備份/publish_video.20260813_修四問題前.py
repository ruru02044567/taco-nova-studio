"""上傳並公開發布到 Taco & Nova 頻道，含合規設定。
用法：python publish_video.py <video.mp4> <title.txt> <desc.txt>
成功時會印出一行含 youtube.com/shorts/ 的網址。
"""
import sys
import time

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

video, title_file, desc_file = sys.argv[1], sys.argv[2], sys.argv[3]
title = open(title_file, encoding="utf-8").read().strip()
desc = open(desc_file, encoding="utf-8").read().strip()

# 發布前擋一次文案格式。8/11 實測：說明第 2 條少了第三人稱劇情描述的兩支片，
# 觀看數從萬級掉到 50~60。那條是演算法唯一讀得懂內容的線索，不能再被誤刪。
# 真的要硬發就加 --force（例如刻意做 A/B 測試時）。
if "--force" not in sys.argv:
    import desc_spec
    ok, problems = desc_spec.check(desc)
    if not ok:
        print("FAILED: 說明文案不符合高流量版格式，拒絕發布")
        for p in problems:
            print("  -", p)
        print("  （確定要照發就加 --force）")
        sys.exit(9)
    print("說明文案格式檢查：通過")

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


TACO_CHANNEL_ID = "UC4Bf0lB05GrYF8Q4l6NnjEA"      # Taco & Nova

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "youtube.com" in p.url and "gemini" not in p.url), None) \
        or ctx.new_page()
    page.bring_to_front()

    # ⚠ 2026-08-11 新增：發布前先確認頻道。
    # 這個 Edge profile 現在有兩個頻道（Taco & Nova ＋ 卡通農場的「小雲硯」），
    # 瀏覽器停在哪個頻道就會發到哪個頻道。
    # 沒有這道檢查的話，只要有人切過頻道忘了切回來，下一支狗狗片就會發到兒童頻道去。
    #
    # ⚠ 8/11 深夜修：原本是 `sleep(10)` 之後看一次 URL 就判定，結果**誤擋了一次發布** ——
    # Studio 冷啟動要 10 秒以上才會從 studio.youtube.com/ 重導向到 /channel/<id>，
    # 那一瞬間 URL 裡當然沒有頻道 ID。檢查沒有錯，是等太短。
    # 改成輪詢等重導向（最多 45 秒），並額外核對畫面上的頻道名稱 ——
    # 只看 URL 會被「還沒導完」騙，兩個都對才算數。這是把檢查改嚴，不是放寬。
    page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
    for _ in range(15):
        time.sleep(3)
        if TACO_CHANNEL_ID in page.url:
            break
    if TACO_CHANNEL_ID not in page.url:
        print("FAILED: 目前作用中的頻道不是 Taco & Nova，中止發布")
        print(f"  現在的 Studio 網址：{page.url[:110]}")
        print("  → 請先到 youtube.com/channel_switcher 手動切回 Taco & Nova 再重跑")
        sys.exit(2)
    chan_name = page.evaluate("""() => {
        for (const s of ['#channel-name', 'ytcp-account-section #entity-name', '#entity-name']) {
            const el = document.querySelector(s);
            if (el && (el.innerText || '').trim()) return el.innerText.trim();
        }
        return null;
    }""")
    if chan_name and "Taco" not in chan_name:
        print(f"FAILED: 網址是 Taco & Nova 但畫面顯示的頻道是「{chan_name}」，中止發布")
        sys.exit(2)
    print(f"頻道確認：Taco & Nova（畫面顯示：{chan_name}）")

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
