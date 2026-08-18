# -*- coding: utf-8 -*-
"""把 Studio 裡卡在「草稿」的影片走完發布（2026-08-18 D9S1 事故的補救）。

事故：publish_video.py 按下「發布」後 sleep 8 秒就宣布 PUBLISHED，
沒有回頭驗證，結果 D9S1 留在草稿。本腳本：
  1. 連現有 Edge（CDP 9222）
  2. 到 Studio 內容頁找標題匹配的草稿列 → 按「編輯草稿」
  3. 下一步×3 → 勾「公開」→ 按「發布」
  4. **重新載入內容頁，驗證該列不再是「草稿」才算成功**（事故的根因就是缺這步）

用法（必須用系統 Python，playwright 在那裡）：
  "C:\\Users\\TUF Gaming\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" _publish_draft.py "標題關鍵字"
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    print("FAILED: 這個 Python 沒有 playwright")
    sys.exit(7)

KEY = sys.argv[1] if len(sys.argv) > 1 else "Red Wine"
STUDIO = "https://studio.youtube.com"


def row_state(page, key):
    """回傳內容清單裡標題含 key 那一列的整列文字（找不到回 None）。"""
    return page.evaluate(
        """(k) => {
            for (const row of document.querySelectorAll('ytcp-video-row')) {
                const t = row.innerText || '';
                if (t.includes(k)) return t;
            }
            return null;
        }""",
        KEY,
    )


def click_in_row(page, key, btntext):
    return page.evaluate(
        """([k, bt]) => {
            for (const row of document.querySelectorAll('ytcp-video-row')) {
                if (!(row.innerText || '').includes(k)) continue;
                for (const b of row.querySelectorAll('button, ytcp-button, tp-yt-paper-button')) {
                    if ((b.innerText || '').trim() === bt) { b.click(); return true; }
                }
            }
            return false;
        }""",
        [key, btntext],
    )


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
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    page.goto(STUDIO + "/", wait_until="domcontentloaded")
    time.sleep(6)
    # Studio 首頁可能不是內容頁，直接點左欄「內容」不可靠，改用網址樣式：
    # 首頁會轉到 /channel/<id>/...，取 channel id 再進 videos 頁
    cur = page.url
    if "/channel/" in cur:
        chan = cur.split("/channel/")[1].split("/")[0]
        page.goto(f"{STUDIO}/channel/{chan}/videos/upload", wait_until="domcontentloaded")

    # 列表是慢慢渲染的，輪詢等到有列為止（上一版等 6 秒就放棄＝誤報找不到）
    for _ in range(20):
        n = page.evaluate("() => document.querySelectorAll('ytcp-video-row').length")
        if n > 0:
            break
        time.sleep(2)
    print("清單列數：", n)

    st = row_state(page, KEY)
    print("目標列狀態：", (st or "找不到").replace("\n", " ｜ ")[:160])
    if st is None:
        print("FAILED: 內容清單找不到目標列")
        sys.exit(1)
    if "草稿" not in st:
        print("這一列已經不是草稿，不用補救。")
        sys.exit(0)

    if not click_in_row(page, KEY, "編輯草稿"):
        print("FAILED: 按不到「編輯草稿」")
        sys.exit(1)
    time.sleep(6)

    # 精靈：下一步×3（逐步等，按不到就再等一輪）
    for i in range(3):
        okc = False
        for _ in range(5):
            if click_exact(page, "下一步"):
                okc = True
                break
            time.sleep(2)
        print(f"下一步 {i+1}/3：{'ok' if okc else 'MISS'}")
        time.sleep(3)

    picked = page.evaluate(
        """() => {
            for (const r of document.querySelectorAll('tp-yt-paper-radio-button')) {
                if ((r.getAttribute('name') || '').toUpperCase() === 'PUBLIC') { r.click(); return true; }
            }
            return false;
        }"""
    )
    print("勾選公開：", picked)
    if not picked:
        print("FAILED: 找不到公開選項")
        sys.exit(1)
    time.sleep(2)

    if not click_exact(page, "發布"):
        print("FAILED: 沒按到發布")
        sys.exit(1)
    time.sleep(8)
    # 發布完通常跳分享畫面 → 關閉
    click_exact(page, "關閉")
    time.sleep(3)

    # ── 事故根因的解：回內容頁驗證 ──
    for attempt in range(6):
        page.goto(page.url.split("?")[0], wait_until="domcontentloaded")
        time.sleep(5)
        st = row_state(page, KEY)
        flat = (st or "").replace("\n", " ｜ ")
        print(f"驗證第 {attempt+1} 次：{flat[:160]}")
        if st and "草稿" not in st:
            print("VERIFIED: 該列已不是草稿 → 發布完成")
            sys.exit(0)
    print("FAILED: 按完發布後清單仍顯示草稿")
    sys.exit(1)
