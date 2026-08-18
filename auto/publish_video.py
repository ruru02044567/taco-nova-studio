"""上傳並公開發布到 Taco & Nova 頻道，含合規設定。
用法：python publish_video.py <video.mp4> <title.txt> <desc.txt>
成功時會印出一行含 youtube.com/shorts/ 的網址。

⚠ 必須用**系統 Python**跑（playwright 裝在那裡），不是 ComfyUI 的 venv：
   C:\\Users\\TUF Gaming\\AppData\\Local\\Programs\\Python\\Python313\\python.exe
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 2026-08-13 加：playwright 找不到時給出「該怎麼辦」，不要只丟 ModuleNotFoundError。
# 8/13 10:37 那次發布失敗就是這個 —— pipeline.py 用 sys.executable 呼叫子腳本，
# 而它自己是被 ComfyUI 的 venv 跑起來的，那個 venv 沒裝 playwright。
# 堆疊訊息看不出根因，浪費了一輪重試。
try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    print("FAILED: 這個 Python 沒有 playwright，無法發布")
    print(f"  目前用的是：{sys.executable}")
    print(r"  → 請改用系統 Python：C:\Users\TUF Gaming\AppData\Local\Programs\Python\Python313\python.exe")
    sys.exit(7)

HERE = Path(__file__).parent

video, title_file, desc_file = sys.argv[1], sys.argv[2], sys.argv[3]
title = open(title_file, encoding="utf-8").read().strip()
desc = open(desc_file, encoding="utf-8").read().strip()

# ── 2026-08-13 加：發布前擋掉已判定不可發的版本 ─────────────────
# 起因：待審核\ 裡同時躺著 5 個 d4s1 版本，其中 3 個已判 REGENERATE 或有幻覺幼犬，
# 但「哪支能發」只寫在 .md 註記和人腦裡，程式讀不到。
# 這支腳本是所有發布的唯一出口（pipeline 自動發、手動發都經過這裡），擋在這最有效。
def _check_not_blacklisted(path):
    f = HERE / "rejected.json"
    if not f.exists():
        return
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  （rejected.json 讀不起來，跳過黑名單檢查）{type(e).__name__}: {e}")
        return
    name = Path(path).name.lower()
    for bucket, label in (("rejected", "已判定不可發"), ("superseded", "已被更新版本取代")):
        for item in data.get(bucket, []):
            if item.get("file", "").lower() == name:
                print(f"FAILED: 這支{label}，拒絕發布")
                print(f"  檔案：{Path(path).name}")
                print(f"  原因：{item.get('reason', '（未記錄）')}")
                if item.get("ref"):
                    print(f"  依據：{item['ref']}")
                print("  （確定要照發就加 --force）")
                sys.exit(8)


# 同一個檔案已經發布過就不要再發一次 —— state.json 記著每支已發影片的路徑。
def _check_not_already_published(path):
    f = HERE / "state.json"
    if not f.exists():
        return
    try:
        state = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return
    name = Path(path).name.lower()
    for key, v in state.items():
        if not isinstance(v, dict) or not v.get("published") or not v.get("url"):
            continue
        if Path(v.get("video", "")).name.lower() == name:
            print(f"FAILED: 這支已經發布過了，拒絕重複發布")
            print(f"  檔案：{Path(path).name}")
            print(f"  {key.upper()} 於 {v.get('at', '?')} 發布：{v['url']}")
            print("  （確定要再發一次就加 --force）")
            sys.exit(8)


if "--force" not in sys.argv:
    _check_not_blacklisted(video)
    _check_not_already_published(video)

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

    # ── 2026-08-18 D9S1 事故補課：按完「發布」不等於發布成功 ──
    # 那天按鈕有按到、也拿到了網址，但影片留在草稿，本腳本仍回報 PUBLISHED。
    # 從此以後：回內容清單，看到這支影片那一列「不是草稿」才算數。
    click_exact(up, "關閉")   # 發布完的分享畫面（沒有也無妨）
    time.sleep(2)
    verify_key = title[:18]
    verified = False
    for attempt in range(6):
        try:
            cur = up.url
            chan = cur.split("/channel/")[1].split("/")[0] if "/channel/" in cur else None
            dest = (f"https://studio.youtube.com/channel/{chan}/videos/upload"
                    if chan else "https://studio.youtube.com/")
            up.goto(dest, wait_until="domcontentloaded")
        except Exception:
            pass
        time.sleep(6)
        row = up.evaluate(
            """(k) => {
                for (const r of document.querySelectorAll('ytcp-video-row')) {
                    const t = r.innerText || '';
                    if (t.includes(k)) return t;
                }
                return null;
            }""",
            verify_key,
        )
        flat = (row or "清單沒有這一列").replace("\n", " ")[:120]
        print(f"  發布後驗證 {attempt + 1}/6：{flat}")
        if row and "草稿" not in row:
            verified = True
            break
    if not verified:
        print("FAILED: 按了發布但內容清單仍是草稿（或找不到），不得視為已發布")
        sys.exit(8)
    print("PUBLISHED", url)
